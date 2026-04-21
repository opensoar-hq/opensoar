from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ingestion.normalize import normalize_alert
from opensoar.logging_context import generate_correlation_id, set_correlation_id
from opensoar.models.alert import Alert

logger = logging.getLogger(__name__)


async def _auto_enrich(session: AsyncSession, alert: Alert) -> None:
    """Materialise observables for ``alert``'s IOCs and enqueue enrichment.

    Every failure is swallowed: enrichment is a best-effort, fire-and-forget
    side effect of ingest and must never block alert creation (issue #66).
    The TTL cache hook (issue #67 / #89) lives inside
    ``opensoar.worker.enrichment.should_enrich``.
    """
    try:
        # Imported lazily so test fixtures can monkey-patch the module cleanly
        # and so the celery_app import only happens once we have work to do.
        from opensoar.worker import enrichment as enrichment_mod

        new_rows = await enrichment_mod.materialise_observables_for_alert(
            session, alert
        )
        await enrichment_mod.schedule_enrichment_for_alert(
            session, alert, new_rows
        )
    except Exception:
        logger.exception(
            "Auto-enrichment failed for alert %s; ingest continuing", alert.id
        )


async def process_webhook(
    session: AsyncSession,
    payload: dict,
    source: str = "webhook",
) -> Alert:
    normalized = normalize_alert(payload, source=source)

    # Deduplication: check if an alert with the same source + source_id exists
    source_id = normalized.get("source_id")
    if source_id:
        result = await session.execute(
            select(Alert).where(
                Alert.source == normalized["source"],
                Alert.source_id == source_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.duplicate_count += 1
            existing.raw_payload = payload
            existing.normalized = normalized
            # Back-fill for alerts ingested before the correlation-id
            # migration so the trace chain is never blank going forward.
            if existing.correlation_id is None:
                existing.correlation_id = generate_correlation_id()
            set_correlation_id(existing.correlation_id)
            await session.flush()
            logger.info(
                f"Deduplicated alert: id={existing.id} source_id={source_id} "
                f"count={existing.duplicate_count} "
                f"correlation_id={existing.correlation_id}"
            )
            return existing

    correlation_id = generate_correlation_id()
    set_correlation_id(correlation_id)
    alert = Alert(
        source=normalized["source"],
        source_id=source_id,
        title=normalized["title"],
        description=normalized.get("description"),
        severity=normalized["severity"],
        status="new",
        raw_payload=payload,
        normalized=normalized,
        source_ip=normalized.get("source_ip"),
        dest_ip=normalized.get("dest_ip"),
        hostname=normalized.get("hostname"),
        rule_name=normalized.get("rule_name"),
        iocs=normalized.get("iocs"),
        tags=normalized.get("tags"),
        partner=normalized.get("partner"),
        correlation_id=correlation_id,
    )
    session.add(alert)
    await session.flush()

    logger.info(
        f"Ingested alert: id={alert.id} title='{alert.title}' "
        f"severity={alert.severity} source={source} "
        f"correlation_id={alert.correlation_id}"
    )

    # Materialise observables from IOCs and fire-and-forget enrichment tasks.
    await _auto_enrich(session, alert)

    return alert

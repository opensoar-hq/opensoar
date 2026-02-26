from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ingestion.normalize import normalize_alert
from opensoar.models.alert import Alert

logger = logging.getLogger(__name__)


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
            await session.flush()
            logger.info(
                f"Deduplicated alert: id={existing.id} source_id={source_id} "
                f"count={existing.duplicate_count}"
            )
            return existing

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
    )
    session.add(alert)
    await session.flush()

    logger.info(
        f"Ingested alert: id={alert.id} title='{alert.title}' "
        f"severity={alert.severity} source={source}"
    )
    return alert

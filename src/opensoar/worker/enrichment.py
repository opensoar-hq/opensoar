"""Automatic observable enrichment.

When an alert is ingested, each newly extracted observable (IP / domain /
hash / URL) gets a fire-and-forget Celery task that dispatches to the
configured enrichment integrations (VirusTotal, AbuseIPDB). Results are
appended to ``Observable.enrichments`` and the ``enrichment_status``
transitions ``pending -> complete`` (or ``failed``).

This module is intentionally decoupled from the rest of the ingest path:

- ``should_enrich(observable)`` is the integration hook where issue #67's
  TTL cache will slot in (today it always returns True).
- ``enqueue_enrichment`` is the single call-site the ingest path uses; it
  swallows all errors so enrichment problems never block alert creation.
- ``_dispatch_enrichments`` is the pure-async worker body; it is mocked in
  tests so the real HTTP clients are never called.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.models.integration import IntegrationInstance
from opensoar.models.observable import Observable
from opensoar.worker.celery_app import celery_app
from opensoar.worker.tasks import _run_async

logger = logging.getLogger(__name__)


# ── In-flight deduplication ──────────────────────────────────────────────────
#
# A short-TTL set keyed by ``(type, value, partner)`` prevents the same
# observable from being enriched twice while a previous task is still running
# (or has just completed). Redis is used in production; in tests and when
# Redis is unavailable we fall back to an in-memory dict so enqueue never
# errors. The TTL is deliberately short — longer caching is issue #67's job.

INFLIGHT_TTL_SECONDS = 300  # 5 minutes

_memory_inflight: dict[str, float] = {}


def _inflight_key(obs_type: str, obs_value: str, partner: str | None) -> str:
    return f"opensoar:enrich:inflight:{partner or '-'}:{obs_type}:{obs_value}"


def _get_redis_client():  # pragma: no cover - exercised only with live Redis
    try:
        import redis  # type: ignore

        from opensoar.config import settings

        return redis.Redis.from_url(settings.redis_url, socket_timeout=0.5)
    except Exception:
        return None


def _mark_inflight(obs_type: str, obs_value: str, partner: str | None) -> bool:
    """Atomically claim the in-flight slot. Returns True if claimed (i.e. the
    caller should enqueue), False if another enrichment already holds the slot.
    """
    key = _inflight_key(obs_type, obs_value, partner)

    client = _get_redis_client()
    if client is not None:
        try:
            # SET NX EX is atomic: claim only if the key does not exist.
            claimed = client.set(name=key, value="1", nx=True, ex=INFLIGHT_TTL_SECONDS)
            return bool(claimed)
        except Exception as exc:  # pragma: no cover - logged, falls back
            logger.debug("Redis in-flight check failed (%s); using in-memory fallback", exc)

    # In-memory fallback: expire stale entries, then claim if absent.
    now = time.monotonic()
    stale = [k for k, expires in _memory_inflight.items() if expires <= now]
    for k in stale:
        _memory_inflight.pop(k, None)
    if key in _memory_inflight:
        return False
    _memory_inflight[key] = now + INFLIGHT_TTL_SECONDS
    return True


def _clear_inflight(obs_type: str, obs_value: str, partner: str | None) -> None:
    key = _inflight_key(obs_type, obs_value, partner)

    client = _get_redis_client()
    if client is not None:
        try:
            client.delete(key)
        except Exception:  # pragma: no cover
            pass

    _memory_inflight.pop(key, None)


def reset_inflight_tracker() -> None:
    """Drop all in-flight state. Intended for tests only."""
    _memory_inflight.clear()
    client = _get_redis_client()
    if client is None:
        return
    try:  # pragma: no cover - depends on running Redis
        for key in client.scan_iter("opensoar:enrich:inflight:*"):
            client.delete(key)
    except Exception:
        pass


# ── Public hook for issue #67 ────────────────────────────────────────────────


def should_enrich(observable: Observable) -> bool:
    """Decide whether ``observable`` should be enriched now.

    Today this always returns ``True``. Issue #67 will plug a TTL cache in
    here (returning ``False`` when a fresh enrichment already exists for the
    same ``(type, value)``). Keep the signature stable.
    """
    return True


# ── Enqueue ──────────────────────────────────────────────────────────────────


def enqueue_enrichment(observable: Observable, partner: str | None = None) -> bool:
    """Fire-and-forget dispatch of an enrichment task for ``observable``.

    Returns True if a task was enqueued, False if it was suppressed (dedup or
    hook returned False) or if the broker call failed. *Never* raises —
    enrichment failures must never block alert ingest.
    """
    if not should_enrich(observable):
        logger.debug(
            "should_enrich hook declined enrichment for %s:%s",
            observable.type,
            observable.value,
        )
        return False

    if not _mark_inflight(observable.type, observable.value, partner):
        logger.debug(
            "Enrichment already in-flight for %s:%s; skipping",
            observable.type,
            observable.value,
        )
        return False

    try:
        enrich_observable_task.delay(
            str(observable.id),
            observable.type,
            observable.value,
            partner,
        )
        return True
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "Failed to enqueue enrichment task for observable %s", observable.id
        )
        _clear_inflight(observable.type, observable.value, partner)
        return False


# ── Integration dispatch ─────────────────────────────────────────────────────


_ENRICHABLE_TYPES = {"ip", "domain", "hash", "url"}


async def _dispatch_enrichments(
    session: AsyncSession, observable: Observable
) -> list[dict[str, Any]]:
    """Look up the observable in every configured enrichment integration.

    Returns a list of enrichment entries (one per source that responded).
    Sources that error are logged and skipped — they do not abort the others.
    """
    entries: list[dict[str, Any]] = []

    # Pull configured integrations for this tenant (partner).
    query = select(IntegrationInstance).where(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.integration_type.in_(["virustotal", "abuseipdb"]),
    )
    if observable.alert_id is not None:
        # Tenant scoping: only integrations for the alert's tenant/partner,
        # plus tenant-agnostic ones with no partner set.
        from opensoar.models.alert import Alert

        alert = await session.get(Alert, observable.alert_id)
        if alert is not None and alert.partner is not None:
            query = query.where(
                (IntegrationInstance.partner == alert.partner)
                | (IntegrationInstance.partner.is_(None))
            )
    result = await session.execute(query)
    instances = result.scalars().all()

    from opensoar.integrations.loader import IntegrationLoader

    loader = IntegrationLoader()
    loader.discover_builtin()

    for instance in instances:
        connector_cls = loader.get_connector(instance.integration_type)
        if connector_cls is None:
            continue
        entry = await _lookup_with_instance(connector_cls, instance, observable)
        if entry is not None:
            entries.append(entry)

    return entries


async def _lookup_with_instance(
    connector_cls: type,
    instance: IntegrationInstance,
    observable: Observable,
) -> dict[str, Any] | None:
    try:
        connector = connector_cls(instance.config)
    except Exception as exc:
        logger.warning(
            "Skipping %s enrichment (config error): %s", instance.integration_type, exc
        )
        return None

    try:
        await connector.connect()
    except Exception as exc:
        logger.warning(
            "Skipping %s enrichment (connect failed): %s",
            instance.integration_type,
            exc,
        )
        return None

    try:
        data = await _invoke_lookup(connector, observable)
        if data is None:
            return None
        return {
            "source": instance.integration_type,
            "data": data,
            "malicious": False,
            "score": None,
        }
    except Exception as exc:
        logger.warning(
            "%s lookup failed for %s:%s: %s",
            instance.integration_type,
            observable.type,
            observable.value,
            exc,
        )
        return None
    finally:
        try:
            await connector.disconnect()
        except Exception:  # pragma: no cover
            pass


async def _invoke_lookup(connector: Any, observable: Observable) -> dict | None:
    obs_type = observable.type
    value = observable.value

    if obs_type == "ip":
        if hasattr(connector, "lookup_ip"):
            return await connector.lookup_ip(value)
        if hasattr(connector, "check_ip"):
            return await connector.check_ip(value)
    elif obs_type == "domain" and hasattr(connector, "lookup_domain"):
        return await connector.lookup_domain(value)
    elif obs_type == "hash" and hasattr(connector, "lookup_hash"):
        return await connector.lookup_hash(value)
    elif obs_type == "url" and hasattr(connector, "lookup_url"):
        return await connector.lookup_url(value)

    return None


# ── Task body ────────────────────────────────────────────────────────────────


async def _run_enrichment(
    *,
    session_factory: Callable,
    observable_id: str,
    obs_type: str,
    obs_value: str,
    partner: str | None,
) -> dict[str, Any]:
    """Execute the enrichment for a single observable inside its own session.

    Exceptions from ``_dispatch_enrichments`` are caught here: the status
    flips to ``failed`` but the task returns normally (fire-and-forget).
    """
    async with session_factory() as session:
        obs = await session.get(Observable, uuid.UUID(observable_id))
        if obs is None:
            logger.warning("Enrichment target %s not found; skipping", observable_id)
            _clear_inflight(obs_type, obs_value, partner)
            return {"status": "missing", "observable_id": observable_id}

        try:
            new_entries = await _dispatch_enrichments(session, obs)
        except Exception:
            logger.exception(
                "Enrichment dispatch failed for %s:%s", obs_type, obs_value
            )
            obs.enrichment_status = "failed"
            await session.commit()
            _clear_inflight(obs_type, obs_value, partner)
            return {"status": "failed", "observable_id": observable_id}

        existing = list(obs.enrichments or [])
        existing.extend(new_entries)
        obs.enrichments = existing
        obs.enrichment_status = "complete"

        await session.commit()

    _clear_inflight(obs_type, obs_value, partner)
    return {
        "status": "complete",
        "observable_id": observable_id,
        "entries": len(new_entries),
    }


@celery_app.task(
    name="opensoar.enrich_observable",
    bind=True,
    max_retries=0,
    ignore_result=True,
)
def enrich_observable_task(
    self,
    observable_id: str,
    obs_type: str,
    obs_value: str,
    partner: str | None = None,
) -> dict[str, Any]:
    """Fire-and-forget enrichment of one observable.

    We deliberately set ``max_retries=0`` — a failure flips
    ``enrichment_status`` to ``failed`` on the observable and is otherwise a
    no-op. Never raises so the broker never retries.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from opensoar.config import settings

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _run():
        try:
            return await _run_enrichment(
                session_factory=session_factory,
                observable_id=observable_id,
                obs_type=obs_type,
                obs_value=obs_value,
                partner=partner,
            )
        finally:
            await engine.dispose()

    try:
        return _run_async(_run())
    except Exception:
        logger.exception(
            "enrich_observable_task crashed for %s; swallowing", observable_id
        )
        _clear_inflight(obs_type, obs_value, partner)
        return {"status": "failed", "observable_id": observable_id}


# ── IOC → observable materialisation ─────────────────────────────────────────


def iter_observable_candidates(iocs: dict | None) -> Iterable[tuple[str, str]]:
    """Yield ``(type, value)`` pairs from an alert's IOC dict.

    Only emits types that are enrichable (``ip``, ``domain``, ``hash``,
    ``url``). Values are trimmed of duplicates within the same call.
    """
    if not iocs:
        return

    mapping = {
        "ips": "ip",
        "domains": "domain",
        "hashes": "hash",
        "urls": "url",
    }
    seen: set[tuple[str, str]] = set()
    for key, values in iocs.items():
        obs_type = mapping.get(key)
        if obs_type is None or obs_type not in _ENRICHABLE_TYPES:
            continue
        for value in values or []:
            if not isinstance(value, str) or not value:
                continue
            pair = (obs_type, value)
            if pair in seen:
                continue
            seen.add(pair)
            yield pair


async def materialise_observables_for_alert(
    session: AsyncSession, alert
) -> list[Observable]:
    """Create Observable rows for every IOC on ``alert`` that isn't already
    tracked for that alert's tenant.

    Returns only the **newly created** rows — callers enqueue enrichment for
    these (already-existing observables should not be re-enriched here, the
    in-flight set handles cross-alert dedup separately).
    """
    new_rows: list[Observable] = []
    for obs_type, value in iter_observable_candidates(alert.iocs):
        # Dedup by (type, value) within the tenant (partner).
        existing_q = select(Observable).where(
            Observable.type == obs_type,
            Observable.value == value,
        )
        existing = (await session.execute(existing_q)).scalar_one_or_none()
        if existing is not None:
            # Link to the current alert if not already
            if existing.alert_id is None:
                existing.alert_id = alert.id
            continue

        obs = Observable(
            type=obs_type,
            value=value,
            source=f"alert:{alert.source}",
            alert_id=alert.id,
            enrichment_status="pending",
            enrichments=[],
        )
        session.add(obs)
        new_rows.append(obs)

    if new_rows:
        await session.flush()
    return new_rows


def schedule_enrichment_for_alert(alert, observables: list[Observable]) -> None:
    """Enqueue an enrichment task for each newly created observable.

    Swallows every exception so enrichment problems never block ingest.
    """
    for obs in observables:
        try:
            enqueue_enrichment(obs, partner=alert.partner)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "Unexpected error while scheduling enrichment for %s", obs.id
            )


__all__ = [
    "INFLIGHT_TTL_SECONDS",
    "enqueue_enrichment",
    "enrich_observable_task",
    "iter_observable_candidates",
    "materialise_observables_for_alert",
    "reset_inflight_tracker",
    "schedule_enrichment_for_alert",
    "should_enrich",
]

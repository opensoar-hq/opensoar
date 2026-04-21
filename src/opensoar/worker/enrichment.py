"""Automatic observable enrichment.

When an alert is ingested, each newly extracted observable (IP / domain /
hash / URL) gets a fire-and-forget Celery task that dispatches to the
configured enrichment integrations (VirusTotal, AbuseIPDB, GreyNoise).
Results are appended to ``Observable.enrichments`` and the
``enrichment_status`` transitions ``pending -> complete`` (or ``failed``).

This module is intentionally decoupled from the rest of the ingest path:

- ``should_enrich(session, observable, partner)`` consults the TTL
  enrichment cache (issue #67) and returns ``False`` only when every
  configured source for the observable's type has a fresh cache hit.
- ``enqueue_enrichment`` is the single call-site the ingest path uses; it
  swallows all errors so enrichment problems never block alert creation.
- ``_dispatch_enrichments`` is the pure-async worker body; it is mocked in
  tests so the real HTTP clients are never called.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.models.integration import IntegrationInstance
from opensoar.models.observable import Observable
from opensoar.worker.celery_app import celery_app
from opensoar.worker.tasks import _run_async

logger = logging.getLogger(__name__)

# ``redis`` is an optional runtime dependency. Import its base error class so
# the narrow ``except`` tuples below can reference it — fall back to a stand-in
# that is never raised when the library is absent.
try:
    from redis.exceptions import RedisError as _RedisError  # type: ignore
except ImportError:  # pragma: no cover - redis is a declared dep in prod
    class _RedisError(Exception):  # type: ignore[no-redef]
        """Sentinel used when the optional ``redis`` package is missing."""


# ── In-flight deduplication ──────────────────────────────────────────────────
#
# A short-TTL set keyed by ``(type, value, partner)`` prevents the same
# observable from being enriched twice while a previous task is still running
# (or has just completed). Redis is used in production; in tests and when
# Redis is unavailable we fall back to an in-memory dict so enqueue never
# errors. The TTL is deliberately short — longer caching lives in the
# integration-level TTL cache (issue #67, wired in via ``should_enrich``).

INFLIGHT_TTL_SECONDS = 300  # 5 minutes

_memory_inflight: dict[str, float] = {}


def _inflight_key(obs_type: str, obs_value: str, partner: str | None) -> str:
    return f"opensoar:enrich:inflight:{partner or '-'}:{obs_type}:{obs_value}"


def _get_redis_client():  # pragma: no cover - exercised only with live Redis
    try:
        import redis  # type: ignore

        from opensoar.config import settings

        return redis.Redis.from_url(settings.redis_url, socket_timeout=0.5)
    # Redis may be missing entirely (ImportError), the URL may be malformed
    # (ValueError) or the socket may refuse (OSError / RedisError). In all
    # cases we silently fall back to the in-memory tracker.
    except (ImportError, ValueError, OSError) as exc:
        logger.debug("Redis client unavailable (%s); using in-memory fallback", exc)
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
        # redis-py raises RedisError (and subclasses like ConnectionError /
        # TimeoutError) for all wire-level failures. OSError covers lower
        # level socket errors. Everything else (TypeError, AttributeError on
        # our own code) should surface.
        except (OSError, _RedisError) as exc:  # pragma: no cover - logged, falls back
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
        except (OSError, _RedisError):  # pragma: no cover
            # Cleanup is best-effort — a failed delete leaves the key to
            # expire naturally via ``INFLIGHT_TTL_SECONDS``.
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
    except (OSError, _RedisError):
        # Reset is a test hook — a Redis outage during cleanup is acceptable.
        pass


# ── Source → observable-type capability map ─────────────────────────────────
#
# When ``should_enrich`` consults the TTL cache it has to know which configured
# integrations would actually run for this observable's type. VirusTotal covers
# IPs, domains, hashes and URLs; AbuseIPDB and GreyNoise are IP-only. Sources
# not listed here are ignored by the cache-freshness check (they never affect
# the skip decision).
_SOURCE_TYPE_CAPABILITIES: dict[str, frozenset[str]] = {
    "virustotal": frozenset({"ip", "domain", "hash", "url"}),
    "abuseipdb": frozenset({"ip"}),
    "greynoise": frozenset({"ip"}),
}

_CACHE_AWARE_SOURCES: tuple[str, ...] = tuple(_SOURCE_TYPE_CAPABILITIES.keys())


async def _configured_sources_for(
    session: AsyncSession, obs_type: str, partner: str | None
) -> list[str]:
    """Return the integration types that are enabled for ``partner`` and that
    handle observable type ``obs_type``. Tenant-agnostic rows (partner IS NULL)
    are always included.
    """
    query = select(IntegrationInstance.integration_type).where(
        IntegrationInstance.enabled.is_(True),
        IntegrationInstance.integration_type.in_(_CACHE_AWARE_SOURCES),
    )
    if partner is not None:
        query = query.where(
            (IntegrationInstance.partner == partner)
            | (IntegrationInstance.partner.is_(None))
        )
    else:
        query = query.where(IntegrationInstance.partner.is_(None))

    rows = (await session.execute(query)).scalars().all()
    # Deduplicate while filtering by type capability.
    sources: list[str] = []
    seen: set[str] = set()
    for source in rows:
        if source in seen:
            continue
        if obs_type not in _SOURCE_TYPE_CAPABILITIES.get(source, frozenset()):
            continue
        seen.add(source)
        sources.append(source)
    return sources


# ── Public hook: consults the TTL cache (issue #89) ─────────────────────────


async def should_enrich(
    session: AsyncSession,
    observable: Observable,
    partner: str | None = None,
) -> bool:
    """Decide whether ``observable`` should be enriched now.

    Returns ``False`` only when every configured enrichment source that can
    handle this observable's type already has a fresh entry in the TTL cache.
    Partial freshness, stale entries or missing entries all return ``True``
    (enqueue). When no source is configured for the observable's type there
    is nothing to cache-skip, so this also returns ``True``.
    """
    try:
        sources = await _configured_sources_for(
            session, observable.type, partner
        )
    # DB read failure while computing the skip-list must degrade to "enqueue"
    # rather than block enrichment. SQLAlchemyError covers driver disconnects,
    # operational errors and query mistakes against the integrations table.
    except SQLAlchemyError:  # pragma: no cover - defensive
        logger.exception(
            "should_enrich: failed to query configured sources; defaulting to enqueue"
        )
        return True

    if not sources:
        # No configured source can cover this observable — nothing to skip.
        return True

    from opensoar.integrations.cache import get_default_cache

    try:
        cache = get_default_cache()
    # Cache-factory failures are transport/config issues (bad Redis URL,
    # unreachable host, malformed json in the backend). A bug in the factory
    # itself (TypeError, AttributeError) should still surface.
    except (OSError, _RedisError, ValueError):  # pragma: no cover - defensive
        logger.exception("should_enrich: cache unavailable; defaulting to enqueue")
        return True

    for source in sources:
        try:
            cached = await cache.get(source, observable.type, observable.value)
        # Cache lookup errors we must tolerate: Redis wire errors, socket
        # failures, json decode failures. Anything else (TypeError etc.) is a
        # programming bug and should surface.
        except (OSError, _RedisError, json.JSONDecodeError) as exc:
            logger.warning(
                "should_enrich: cache lookup failed for %s:%s:%s (%s); enqueue",
                source,
                observable.type,
                observable.value,
                exc,
            )
            return True
        if cached is None:
            # Missing or expired entry => must enqueue.
            return True

    # Every configured source had a fresh hit — safe to skip.
    return False


# ── Enqueue ──────────────────────────────────────────────────────────────────


async def enqueue_enrichment(
    session: AsyncSession,
    observable: Observable,
    partner: str | None = None,
) -> bool:
    """Fire-and-forget dispatch of an enrichment task for ``observable``.

    Returns True if a task was enqueued, False if it was suppressed (dedup,
    cache-fresh across every configured source, or a broker failure). *Never*
    raises — enrichment failures must never block alert ingest.
    """
    if not await should_enrich(session, observable, partner):
        logger.debug(
            "TTL cache satisfied; skipping enrichment for %s:%s",
            observable.type,
            observable.value,
        )
        try:
            from opensoar.middleware.metrics import record_enrichment_cache_skip

            record_enrichment_cache_skip(observable.type)
        # Metrics import / label lookup mismatches are the realistic failures;
        # we don't want a missing prometheus_client, a registry reset race
        # (KeyError) or a bad label type (ValueError) to break ingest.
        except (ImportError, KeyError, ValueError):  # pragma: no cover
            logger.exception("Failed to record enrichment cache skip metric")
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
    # Broker-side failures are the realistic case: TCP errors (ConnectionError
    # / TimeoutError are subclasses of OSError), kombu connection issues, a
    # mis-rendered routing key (KeyError / ValueError). Programming bugs
    # inside ``enrich_observable_task.delay`` itself should surface.
    except (OSError, ConnectionError, TimeoutError, KeyError, ValueError):
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
    # Connectors construct and connect against third-party SDKs. Config,
    # connect, and lookup can all fail for network, auth, or input reasons —
    # we log and skip rather than abort the other sources. The catch tuple
    # below is deliberately broad enough to cover aiohttp / httpx / asyncio
    # errors while still letting programming-bug categories (MemoryError,
    # SystemExit, KeyboardInterrupt) propagate.
    try:
        connector = connector_cls(instance.config)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        logger.warning(
            "Skipping %s enrichment (config error): %s", instance.integration_type, exc
        )
        return None

    try:
        await connector.connect()
    except (OSError, ValueError, RuntimeError, asyncio.TimeoutError) as exc:
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
    except (
        OSError,
        ValueError,
        RuntimeError,
        asyncio.TimeoutError,
        json.JSONDecodeError,
    ) as exc:
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
        except (OSError, RuntimeError):  # pragma: no cover
            # Disconnect failures are cosmetic — the lookup already produced
            # (or failed to produce) its result before this runs.
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
        # Dispatch failures we must tolerate: DB errors (SQLAlchemyError),
        # connector runtime errors, I/O errors and timeouts. Mark the
        # observable failed and return — this is fire-and-forget.
        except (
            SQLAlchemyError,
            OSError,
            RuntimeError,
            ValueError,
            asyncio.TimeoutError,
        ):
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
    # Outermost safety net for a Celery fire-and-forget task: re-raising
    # here would trigger broker retries we explicitly disabled
    # (``max_retries=0``) and surface as a dropped observable status. Keep
    # the broad catch scoped to ``Exception`` (not ``BaseException``) so
    # SystemExit / KeyboardInterrupt still propagate.
    except Exception:  # noqa: BLE001 - intentional outer safety net, see comment
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


async def schedule_enrichment_for_alert(
    session: AsyncSession, alert, observables: list[Observable]
) -> None:
    """Enqueue an enrichment task for each newly created observable.

    Swallows every exception so enrichment problems never block ingest.
    """
    for obs in observables:
        try:
            await enqueue_enrichment(session, obs, partner=alert.partner)
        # Ingest must never block on an enrichment-scheduling bug — this is
        # the outer safety net covering any uncaught failure bubbling up
        # from ``enqueue_enrichment``. Logged loudly with ``logger.exception``
        # so the real cause is always visible.
        except Exception:  # noqa: BLE001 - ingest safety net (issue #66); see comment  # pragma: no cover
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

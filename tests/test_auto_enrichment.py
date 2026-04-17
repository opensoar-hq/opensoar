"""Tests for automatic observable enrichment on alert ingest.

Covers issue #66:
  (a) Alert ingest creates observables and enqueues one enrichment task per
      newly created observable.
  (b) The enrichment task writes an entry to ``observable.enrichments`` and
      flips ``enrichment_status`` from ``pending`` to ``complete``.
  (c) A duplicate dispatch for the same ``(type, value)`` within the in-flight
      window is suppressed.
  (d) Enrichment failures do not block alert ingest.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ingestion.webhook import process_webhook
from opensoar.models.observable import Observable


# ── (a) ingest enqueues one task per new observable ──────────────────────────


class TestIngestEnqueuesEnrichment:
    async def test_creates_observables_and_enqueues_task_per_ioc(
        self, session: AsyncSession
    ):
        """Ingesting an alert with multiple IOCs creates one observable per IOC
        and enqueues exactly one enrichment task per newly created observable.
        """
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()

        payload = {
            "source_id": f"enq-{uuid.uuid4().hex[:8]}",
            "rule_name": "Malware Detected",
            "severity": "high",
            "source_ip": "203.0.113.10",
            "file_hash": "d41d8cd98f00b204e9800998ecf8427e",
        }

        captured: list[tuple] = []

        def fake_delay(observable_id, obs_type, obs_value, partner=None):
            captured.append((observable_id, obs_type, obs_value, partner))

        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay",
            side_effect=fake_delay,
        ):
            alert = await process_webhook(session, payload, source="webhook")
            await session.commit()

        # Observables were created from IOCs (linked to alert)
        result = await session.execute(
            select(Observable).where(Observable.alert_id == alert.id)
        )
        observables = result.scalars().all()
        obs_values = {o.value for o in observables}
        assert "203.0.113.10" in obs_values
        assert "d41d8cd98f00b204e9800998ecf8427e" in obs_values

        # One task per newly created observable
        assert len(captured) == len(observables)
        dispatched_values = {c[2] for c in captured}
        assert dispatched_values == obs_values

    async def test_enqueue_failure_does_not_block_ingest(
        self, session: AsyncSession
    ):
        """If Celery enqueue itself raises, the alert must still be persisted."""
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()

        payload = {
            "source_id": f"block-{uuid.uuid4().hex[:8]}",
            "rule_name": "IOC Alert",
            "severity": "medium",
            "source_ip": "198.51.100.77",
        }

        def blow_up(*_args, **_kwargs):
            raise RuntimeError("broker is down")

        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay",
            side_effect=blow_up,
        ):
            alert = await process_webhook(session, payload, source="webhook")
            await session.commit()

        assert alert.id is not None
        assert alert.title == "IOC Alert"
        # Observable row was still written despite the dispatch failure
        result = await session.execute(
            select(Observable).where(Observable.alert_id == alert.id)
        )
        observables = result.scalars().all()
        assert any(o.value == "198.51.100.77" for o in observables)


# ── (c) duplicate dispatch is suppressed ─────────────────────────────────────


class TestDuplicateDispatchSuppression:
    async def test_duplicate_dispatch_suppressed_within_window(
        self, session: AsyncSession
    ):
        """Re-ingesting the same IOC while a previous enrichment is in-flight
        must not enqueue a second task for the same (type, value).
        """
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()

        payload1 = {
            "source_id": f"dup-a-{uuid.uuid4().hex[:8]}",
            "rule_name": "First Alert",
            "severity": "high",
            "source_ip": "10.200.200.200",
        }
        payload2 = {
            "source_id": f"dup-b-{uuid.uuid4().hex[:8]}",
            "rule_name": "Second Alert",
            "severity": "high",
            "source_ip": "10.200.200.200",
        }

        calls: list[tuple] = []

        def fake_delay(observable_id, obs_type, obs_value, partner=None):
            calls.append((obs_type, obs_value))

        with patch(
            "opensoar.worker.enrichment.enrich_observable_task.delay",
            side_effect=fake_delay,
        ):
            await process_webhook(session, payload1, source="webhook")
            await session.commit()
            await process_webhook(session, payload2, source="webhook")
            await session.commit()

        ip_dispatches = [c for c in calls if c == ("ip", "10.200.200.200")]
        assert len(ip_dispatches) == 1, (
            f"Expected one dispatch for (ip, 10.200.200.200); got {calls}"
        )

    async def test_should_enrich_hook_defaults_true(self):
        """The ``should_enrich`` hook is the integration point for issue #67's
        TTL cache. Today it must default to True so every new observable is
        enriched.
        """
        from opensoar.worker import enrichment

        class _Stub:
            type = "ip"
            value = "1.2.3.4"
            enrichments = None
            enrichment_status = "pending"

        assert enrichment.should_enrich(_Stub()) is True


# ── (b) task writes enrichment + flips status ────────────────────────────────


class TestEnrichmentTaskWritesResults:
    async def test_task_writes_enrichment_and_marks_complete(
        self, session: AsyncSession, db_session_factory
    ):
        """Running the enrichment task for a pending observable should append
        an enrichment entry and flip the status to ``complete``.
        """
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()

        obs = Observable(
            type="ip",
            value="192.0.2.55",
            source="test",
            enrichment_status="pending",
            enrichments=[],
        )
        session.add(obs)
        await session.commit()
        await session.refresh(obs)
        obs_id = obs.id

        async def fake_dispatch(session_, observable):
            return [
                {
                    "source": "virustotal",
                    "data": {"malicious": 2, "total": 70},
                    "malicious": True,
                    "score": 2.8,
                }
            ]

        with patch.object(enrichment, "_dispatch_enrichments", side_effect=fake_dispatch):
            await enrichment._run_enrichment(
                session_factory=db_session_factory,
                observable_id=str(obs_id),
                obs_type="ip",
                obs_value="192.0.2.55",
                partner=None,
            )

        async with db_session_factory() as s:
            refreshed = await s.get(Observable, obs_id)
            assert refreshed.enrichment_status == "complete"
            assert refreshed.enrichments and len(refreshed.enrichments) == 1
            assert refreshed.enrichments[0]["source"] == "virustotal"

    async def test_task_marks_failed_when_all_sources_error(
        self, session: AsyncSession, db_session_factory
    ):
        """If every configured source raises, status should flip to ``failed``
        but the task itself must not propagate the exception (fire-and-forget).
        """
        from opensoar.worker import enrichment

        enrichment.reset_inflight_tracker()

        obs = Observable(
            type="ip",
            value="192.0.2.66",
            source="test",
            enrichment_status="pending",
            enrichments=[],
        )
        session.add(obs)
        await session.commit()
        await session.refresh(obs)
        obs_id = obs.id

        async def boom(session_, observable):
            raise RuntimeError("vt unreachable")

        with patch.object(enrichment, "_dispatch_enrichments", side_effect=boom):
            await enrichment._run_enrichment(
                session_factory=db_session_factory,
                observable_id=str(obs_id),
                obs_type="ip",
                obs_value="192.0.2.66",
                partner=None,
            )

        async with db_session_factory() as s:
            refreshed = await s.get(Observable, obs_id)
            assert refreshed.enrichment_status == "failed"


@pytest.fixture(autouse=True)
def _reset_inflight():
    """Ensure tests do not leak in-flight state across each other."""
    from opensoar.worker import enrichment

    enrichment.reset_inflight_tracker()
    yield
    enrichment.reset_inflight_tracker()

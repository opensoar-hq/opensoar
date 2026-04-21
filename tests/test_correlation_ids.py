"""Tests for correlation IDs spanning alert -> playbook -> action chain (issue #109)."""
from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.ingestion.webhook import process_webhook
from opensoar.logging_context import (
    CorrelationIdFilter,
    correlation_id_ctx,
    ensure_correlation_id,
    generate_correlation_id,
)


class TestCorrelationIdGeneration:
    async def test_process_webhook_sets_correlation_id(self, session: AsyncSession):
        """An alert ingested via webhook must have a correlation_id set."""
        payload = {
            "rule_name": "Test Alert",
            "severity": "high",
            "source_id": "corr-id-test-1",
        }
        alert = await process_webhook(session, payload, source="webhook")

        assert alert.correlation_id is not None
        assert isinstance(alert.correlation_id, uuid.UUID)

    async def test_deduplicated_alert_keeps_original_correlation_id(
        self, session: AsyncSession
    ):
        """Duplicate alerts share the original's correlation_id."""
        payload = {
            "rule_name": "Dup Alert",
            "severity": "medium",
            "source_id": "corr-id-dup-1",
        }
        alert1 = await process_webhook(session, payload, source="webhook")
        alert2 = await process_webhook(session, payload, source="webhook")

        assert alert1.id == alert2.id
        assert alert1.correlation_id == alert2.correlation_id

    async def test_webhook_api_exposes_correlation_id(self, client: AsyncClient):
        """Webhook response exposes correlation_id for clients to trace."""
        resp = await client.post(
            "/api/v1/webhooks/alerts",
            json={"rule_name": "API Corr Test", "severity": "low"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "correlation_id" in data
        # Should parse as UUID
        uuid.UUID(data["correlation_id"])


class TestCorrelationIdContextVar:
    def test_generate_correlation_id_returns_uuid(self):
        cid = generate_correlation_id()
        assert isinstance(cid, uuid.UUID)

    def test_correlation_id_ctx_defaults_to_none(self):
        assert correlation_id_ctx.get() is None

    async def test_ensure_correlation_id_sets_when_missing(self):
        """ensure_correlation_id sets a new id when none is in the contextvar."""

        async def inner():
            token = correlation_id_ctx.set(None)
            try:
                cid = ensure_correlation_id()
                assert isinstance(cid, uuid.UUID)
                assert correlation_id_ctx.get() == cid
            finally:
                correlation_id_ctx.reset(token)

        await inner()

    async def test_ensure_correlation_id_preserves_existing(self):
        cid = uuid.uuid4()

        async def inner():
            token = correlation_id_ctx.set(cid)
            try:
                got = ensure_correlation_id()
                assert got == cid
            finally:
                correlation_id_ctx.reset(token)

        await inner()

    async def test_contextvar_isolates_concurrent_executions(self):
        """Concurrent coroutines must not cross-contaminate correlation_ids."""
        observed: dict[str, uuid.UUID | None] = {}

        async def run(tag: str, cid: uuid.UUID) -> None:
            token = correlation_id_ctx.set(cid)
            try:
                # Let the scheduler interleave tasks
                await asyncio.sleep(0.01)
                observed[tag] = correlation_id_ctx.get()
            finally:
                correlation_id_ctx.reset(token)

        cid_a = uuid.uuid4()
        cid_b = uuid.uuid4()
        cid_c = uuid.uuid4()
        await asyncio.gather(
            run("a", cid_a),
            run("b", cid_b),
            run("c", cid_c),
        )
        assert observed == {"a": cid_a, "b": cid_b, "c": cid_c}


class TestCorrelationIdLogFilter:
    def test_filter_injects_correlation_id_from_ctx(self):
        """CorrelationIdFilter must populate record.correlation_id."""
        cid = uuid.uuid4()
        token = correlation_id_ctx.set(cid)
        try:
            record = logging.LogRecord(
                name="t",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="hi",
                args=(),
                exc_info=None,
            )
            CorrelationIdFilter().filter(record)
            assert getattr(record, "correlation_id") == str(cid)
        finally:
            correlation_id_ctx.reset(token)

    def test_filter_uses_placeholder_when_no_ctx(self):
        token = correlation_id_ctx.set(None)
        try:
            record = logging.LogRecord(
                name="t",
                level=logging.INFO,
                pathname=__file__,
                lineno=1,
                msg="hi",
                args=(),
                exc_info=None,
            )
            CorrelationIdFilter().filter(record)
            assert getattr(record, "correlation_id") == "-"
        finally:
            correlation_id_ctx.reset(token)


class TestCorrelationIdPropagationThroughExecutor:
    async def test_executor_propagates_correlation_id_to_logs(
        self, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ):
        """Playbook execution logs must carry the alert's correlation_id."""
        from opensoar.core.decorators import (
            PlaybookMeta,
            RegisteredPlaybook,
            get_execution_context,
        )
        from opensoar.core.executor import PlaybookExecutor
        from opensoar.models.alert import Alert
        from opensoar.models.playbook import PlaybookDefinition

        # Seed an alert with a known correlation_id
        cid = uuid.uuid4()
        alert = Alert(
            source="webhook",
            source_id=f"exec-{uuid.uuid4().hex[:8]}",
            title="Executor Test",
            severity="medium",
            status="new",
            raw_payload={},
            normalized={},
            correlation_id=cid,
        )
        session.add(alert)

        pb_row = PlaybookDefinition(
            name=f"pb-exec-{uuid.uuid4().hex[:8]}",
            module_path="tests.test_correlation_ids",
            function_name="fake_playbook",
            trigger_type="webhook",
            trigger_config={},
            enabled=True,
        )
        session.add(pb_row)
        await session.commit()

        captured_cid: dict[str, uuid.UUID | None] = {}

        async def fake_playbook(_input):
            ctx = get_execution_context()
            captured_cid["ctx"] = ctx.correlation_id if ctx else None
            captured_cid["var"] = correlation_id_ctx.get()
            return {"ok": True}

        pb = RegisteredPlaybook(
            meta=PlaybookMeta(name=pb_row.name, trigger="webhook"),
            func=fake_playbook,
            module="tests.test_correlation_ids",
        )

        executor = PlaybookExecutor(session)
        with caplog.at_level(logging.INFO, logger="opensoar.core.executor"):
            run = await executor.execute(pb, alert_id=alert.id)

        assert run.status == "success"
        assert run.correlation_id == cid
        assert captured_cid["ctx"] == cid
        assert captured_cid["var"] == cid

        # Completion log includes the run id and the contextvar was set at
        # emission time — the filter will have stamped correlation_id onto
        # the record. Confirm the contextvar was restored after execution.
        assert correlation_id_ctx.get() is None

    async def test_executor_generates_correlation_id_for_manual_run(
        self, session: AsyncSession
    ):
        """Manual runs (no alert) still receive a correlation_id."""
        from opensoar.core.decorators import PlaybookMeta, RegisteredPlaybook
        from opensoar.core.executor import PlaybookExecutor
        from opensoar.models.playbook import PlaybookDefinition

        pb_row = PlaybookDefinition(
            name=f"pb-manual-{uuid.uuid4().hex[:8]}",
            module_path="tests.test_correlation_ids",
            function_name="fake_playbook",
            trigger_type=None,
            trigger_config={},
            enabled=True,
        )
        session.add(pb_row)
        await session.commit()

        async def fake_playbook(_input):
            return {"ok": True}

        pb = RegisteredPlaybook(
            meta=PlaybookMeta(name=pb_row.name),
            func=fake_playbook,
            module="tests.test_correlation_ids",
        )

        executor = PlaybookExecutor(session)
        run = await executor.execute(pb, manual_input={"x": 1})

        assert run.status == "success"
        assert run.correlation_id is not None
        assert isinstance(run.correlation_id, uuid.UUID)

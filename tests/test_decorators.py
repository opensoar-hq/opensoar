"""Tests for @action and @playbook decorators."""
from __future__ import annotations

import asyncio

import pytest

from opensoar.core.decorators import (
    ExecutionContext,
    action,
    get_playbook_registry,
    playbook,
    set_execution_context,
)


class TestActionDecorator:
    async def test_basic_action_call(self):
        @action(name="test.basic")
        async def my_action(x: int) -> dict:
            return {"result": x * 2}

        result = await my_action(5)
        assert result == {"result": 10}

    async def test_action_records_success(self):
        recorded = []

        async def recorder(**kwargs):
            recorded.append(kwargs)

        ctx = ExecutionContext(run_id="test-run", record_action=recorder)
        set_execution_context(ctx)

        @action(name="test.record")
        async def my_action() -> dict:
            return {"ok": True}

        await my_action()
        set_execution_context(None)

        assert len(recorded) == 1
        assert recorded[0]["action_name"] == "test.record"
        assert recorded[0]["status"] == "success"

    async def test_action_records_failure(self):
        recorded = []

        async def recorder(**kwargs):
            recorded.append(kwargs)

        ctx = ExecutionContext(run_id="test-run", record_action=recorder)
        set_execution_context(ctx)

        @action(name="test.fail")
        async def failing_action():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await failing_action()
        set_execution_context(None)

        assert len(recorded) == 1
        assert recorded[0]["status"] == "failed"
        assert "boom" in recorded[0]["error"]

    async def test_action_timeout(self):
        @action(name="test.timeout", timeout=1)
        async def slow_action():
            await asyncio.sleep(10)

        recorded = []

        async def recorder(**kwargs):
            recorded.append(kwargs)

        ctx = ExecutionContext(run_id="test-run", record_action=recorder)
        set_execution_context(ctx)

        with pytest.raises(asyncio.TimeoutError):
            await slow_action()
        set_execution_context(None)

    async def test_action_retry(self):
        """Retry only works within an execution context."""
        call_count = 0

        @action(name="test.retry", retries=2, retry_backoff=0.01)
        async def flaky_action():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("not yet")
            return {"ok": True}

        recorded = []

        async def recorder(**kwargs):
            recorded.append(kwargs)

        ctx = ExecutionContext(run_id="retry-run", record_action=recorder)
        set_execution_context(ctx)

        result = await flaky_action()
        set_execution_context(None)

        assert result == {"ok": True}
        assert call_count == 3

    async def test_action_meta_attached(self):
        @action(name="test.meta", timeout=30, retries=1)
        async def my_action():
            pass

        assert hasattr(my_action, "_soar_action")
        assert my_action._soar_action.name == "test.meta"
        assert my_action._soar_action.timeout == 30
        assert my_action._soar_action.retries == 1


class TestPlaybookDecorator:
    def test_playbook_registers(self):
        @playbook(trigger="webhook", name="test_pb_register")
        async def my_playbook(alert):
            pass

        registry = get_playbook_registry()
        assert "test_pb_register" in registry
        assert registry["test_pb_register"].meta.trigger == "webhook"

    def test_playbook_with_conditions(self):
        @playbook(
            trigger="webhook",
            conditions={"severity": ["high", "critical"]},
            name="test_pb_conditions",
        )
        async def conditional_pb(alert):
            pass

        registry = get_playbook_registry()
        pb = registry["test_pb_conditions"]
        assert pb.meta.conditions == {"severity": ["high", "critical"]}

    def test_playbook_meta_attached(self):
        @playbook(trigger="elastic", description="Test playbook", name="test_pb_meta")
        async def described_pb(alert):
            pass

        assert hasattr(described_pb, "_soar_playbook")
        assert described_pb._soar_playbook.description == "Test playbook"

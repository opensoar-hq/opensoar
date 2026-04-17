"""Tests for Celery queue routing (issue #85: clustered workers).

Verifies:
- ``@playbook(priority=...)`` accepts/validates priority, default is "default".
- ``execute_playbook_task`` routes to the playbook's declared queue.
- ``execute_playbook_task`` accepts an explicit ``priority`` override.
- ``enrich_observable_task`` is routed to the ``low`` queue via task_routes.
- ``celery_app`` declares the ``high`` / ``default`` / ``low`` queues.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from opensoar.core.decorators import (
    PlaybookMeta,
    get_playbook_registry,
    playbook,
)
from opensoar.worker.celery_app import celery_app
from opensoar.worker.routing import (
    QUEUE_DEFAULT,
    QUEUE_HIGH,
    QUEUE_LOW,
    VALID_PRIORITIES,
    queue_for_playbook,
    queue_for_priority,
)


class TestPlaybookPriorityDecorator:
    def test_default_priority_is_default(self):
        @playbook(trigger="webhook", name="test_prio_default")
        async def pb(alert):
            pass

        meta: PlaybookMeta = get_playbook_registry()["test_prio_default"].meta
        assert meta.priority == "default"

    def test_high_priority(self):
        @playbook(trigger="webhook", name="test_prio_high", priority="high")
        async def pb(alert):
            pass

        meta: PlaybookMeta = get_playbook_registry()["test_prio_high"].meta
        assert meta.priority == "high"

    def test_low_priority(self):
        @playbook(trigger="webhook", name="test_prio_low", priority="low")
        async def pb(alert):
            pass

        meta: PlaybookMeta = get_playbook_registry()["test_prio_low"].meta
        assert meta.priority == "low"

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError, match="priority"):

            @playbook(trigger="webhook", name="test_prio_invalid", priority="urgent")
            async def pb(alert):
                pass


class TestRoutingHelpers:
    def test_valid_priorities_set(self):
        assert VALID_PRIORITIES == {QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW}

    def test_queue_for_priority_maps_directly(self):
        assert queue_for_priority("high") == QUEUE_HIGH
        assert queue_for_priority("default") == QUEUE_DEFAULT
        assert queue_for_priority("low") == QUEUE_LOW

    def test_queue_for_priority_unknown_falls_back_to_default(self):
        assert queue_for_priority("bogus") == QUEUE_DEFAULT
        assert queue_for_priority(None) == QUEUE_DEFAULT

    def test_queue_for_playbook_reads_meta_priority(self):
        @playbook(trigger="webhook", name="test_q_high_pb", priority="high")
        async def pb_high(alert):
            pass

        assert queue_for_playbook("test_q_high_pb") == QUEUE_HIGH

    def test_queue_for_playbook_unknown_name_defaults(self):
        assert queue_for_playbook("nonexistent_pb_xyz") == QUEUE_DEFAULT


class TestExecutePlaybookTaskRouting:
    def test_delay_routes_to_playbook_declared_queue(self):
        @playbook(trigger="webhook", name="test_exec_high", priority="high")
        async def pb_high(alert):
            pass

        from opensoar.worker.tasks import execute_playbook_task

        with patch.object(execute_playbook_task, "apply_async") as mock_apply:
            execute_playbook_task.delay("test_exec_high", "alert-123")

        mock_apply.assert_called_once()
        kwargs = mock_apply.call_args.kwargs
        assert kwargs.get("queue") == QUEUE_HIGH
        assert kwargs.get("args") == ("test_exec_high", "alert-123")

    def test_delay_default_priority_goes_to_default_queue(self):
        @playbook(trigger="webhook", name="test_exec_default")
        async def pb_default(alert):
            pass

        from opensoar.worker.tasks import execute_playbook_task

        with patch.object(execute_playbook_task, "apply_async") as mock_apply:
            execute_playbook_task.delay("test_exec_default")

        kwargs = mock_apply.call_args.kwargs
        assert kwargs.get("queue") == QUEUE_DEFAULT

    def test_explicit_priority_override_wins(self):
        @playbook(trigger="webhook", name="test_exec_override", priority="low")
        async def pb_low(alert):
            pass

        from opensoar.worker.tasks import execute_playbook_task

        with patch.object(execute_playbook_task, "apply_async") as mock_apply:
            # Override the playbook's low with high
            execute_playbook_task.delay(
                "test_exec_override", "alert-xyz", priority="high"
            )

        kwargs = mock_apply.call_args.kwargs
        assert kwargs.get("queue") == QUEUE_HIGH
        # priority should not appear as a task arg, only as routing hint
        assert kwargs.get("args") == ("test_exec_override", "alert-xyz")

    def test_unknown_playbook_falls_back_to_default_queue(self):
        from opensoar.worker.tasks import execute_playbook_task

        with patch.object(execute_playbook_task, "apply_async") as mock_apply:
            execute_playbook_task.delay("not_registered_pb")

        kwargs = mock_apply.call_args.kwargs
        assert kwargs.get("queue") == QUEUE_DEFAULT


class TestExecuteSequenceTaskRouting:
    def test_sequence_uses_highest_priority_across_playbooks(self):
        @playbook(trigger="webhook", name="test_seq_low", priority="low")
        async def pb_low(alert):
            pass

        @playbook(trigger="webhook", name="test_seq_high", priority="high")
        async def pb_high(alert):
            pass

        from opensoar.worker.tasks import execute_playbook_sequence_task

        with patch.object(execute_playbook_sequence_task, "apply_async") as mock_apply:
            execute_playbook_sequence_task.delay(
                ["test_seq_low", "test_seq_high"], "alert-a"
            )

        kwargs = mock_apply.call_args.kwargs
        # "high" beats "low": sequence must run on the hottest queue needed.
        assert kwargs.get("queue") == QUEUE_HIGH


class TestEnrichObservableRouting:
    def test_enrich_task_routed_to_low_via_task_routes(self):
        routes = celery_app.conf.task_routes or {}
        assert "opensoar.enrich_observable" in routes
        assert routes["opensoar.enrich_observable"]["queue"] == QUEUE_LOW


class TestCeleryQueueDeclaration:
    def test_all_three_queues_declared(self):
        queue_names = {q.name for q in (celery_app.conf.task_queues or [])}
        assert {QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW}.issubset(queue_names)

    def test_default_queue_is_default(self):
        assert celery_app.conf.task_default_queue == QUEUE_DEFAULT

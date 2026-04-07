from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from opensoar import get_current_alert_id, playbook, resolve_current_alert
from opensoar.core.decorators import get_playbook_registry
from opensoar.core.executor import PlaybookExecutor
from opensoar.models.activity import Activity
from opensoar.models.alert import Alert
from opensoar.models.playbook import PlaybookDefinition
from opensoar.worker.tasks import _execute_sequence


class TestPlaybookRuntime:
    async def test_resolve_current_alert_updates_bound_alert(self, session):
        @playbook(trigger="webhook", name="test_resolve_current_alert")
        async def resolve_playbook(alert):
            assert get_current_alert_id() == str(alert.id)
            return await resolve_current_alert(
                determination="benign",
                reason="Recovered automatically",
                activity_action="playbook_auto_resolved",
                activity_detail="Playbook resolved the alert after remediation",
            )

        alert = Alert(
            source="webhook",
            source_id=f"runtime-{uuid.uuid4().hex[:8]}",
            title="Runtime Resolve",
            description="Test alert",
            severity="low",
            status="new",
            raw_payload={"rule_name": "Runtime Resolve", "severity": "low"},
            normalized={"severity": "low", "source": "webhook"},
        )
        session.add(alert)
        await session.flush()

        session.add(
            PlaybookDefinition(
                name="test_resolve_current_alert",
                description="Runtime resolve test",
                module_path=resolve_playbook.__module__,
                function_name=resolve_playbook.__name__,
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
            )
        )
        await session.commit()

        executor = PlaybookExecutor(session)
        result = await executor.execute(
            get_playbook_registry()["test_resolve_current_alert"],
            alert_id=alert.id,
        )

        refreshed = (
            await session.execute(select(Alert).where(Alert.id == alert.id))
        ).scalar_one()
        assert result.status == "success"
        assert refreshed.status == "resolved"
        assert refreshed.determination == "benign"
        assert refreshed.resolve_reason == "Recovered automatically"

        activities = (
            await session.execute(
                select(Activity).where(Activity.alert_id == alert.id).order_by(Activity.created_at.asc())
            )
        ).scalars().all()
        assert [activity.action for activity in activities] == [
            "status_change",
            "determination_set",
            "playbook_auto_resolved",
        ]

    async def test_resolve_current_alert_requires_bound_alert(self):
        with pytest.raises(RuntimeError, match="No current alert"):
            await resolve_current_alert(determination="benign")

    async def test_resolve_current_alert_rejects_unknown_determination(self, session):
        @playbook(trigger="webhook", name="test_resolve_invalid_determination")
        async def invalid_resolve(alert):
            return await resolve_current_alert(determination="unknown")

        alert = Alert(
            source="webhook",
            source_id=f"runtime-{uuid.uuid4().hex[:8]}",
            title="Runtime Invalid Resolve",
            description="Test alert",
            severity="low",
            status="new",
            raw_payload={"rule_name": "Runtime Invalid Resolve", "severity": "low"},
            normalized={"severity": "low", "source": "webhook"},
        )
        session.add(alert)
        await session.flush()

        session.add(
            PlaybookDefinition(
                name="test_resolve_invalid_determination",
                description="Invalid runtime resolve test",
                module_path=invalid_resolve.__module__,
                function_name=invalid_resolve.__name__,
                trigger_type="webhook",
                trigger_config={},
                enabled=True,
            )
        )
        await session.commit()

        executor = PlaybookExecutor(session)
        result = await executor.execute(
            get_playbook_registry()["test_resolve_invalid_determination"],
            alert_id=alert.id,
        )

        assert result.status == "failed"
        assert "determination must be one of" in (result.error or "")

    async def test_execute_sequence_runs_playbooks_in_order(self, session, db_session_factory):
        execution_log: list[str] = []

        @playbook(trigger="webhook", name="sequence_first", order=10)
        async def first_playbook(alert):
            execution_log.append("first")
            return {"ok": True}

        @playbook(trigger="webhook", name="sequence_second", order=20)
        async def second_playbook(alert):
            execution_log.append("second")
            return {"ok": True}

        alert = Alert(
            source="webhook",
            source_id=f"sequence-{uuid.uuid4().hex[:8]}",
            title="Sequence Alert",
            description="Sequence test alert",
            severity="low",
            status="new",
            raw_payload={"rule_name": "Sequence Alert", "severity": "low"},
            normalized={"severity": "low", "source": "webhook"},
        )
        session.add(alert)
        await session.flush()

        session.add_all(
            [
                PlaybookDefinition(
                    name="sequence_first",
                    description="Sequence first",
                    execution_order=10,
                    module_path=first_playbook.__module__,
                    function_name=first_playbook.__name__,
                    trigger_type="webhook",
                    trigger_config={},
                    enabled=True,
                ),
                PlaybookDefinition(
                    name="sequence_second",
                    description="Sequence second",
                    execution_order=20,
                    module_path=second_playbook.__module__,
                    function_name=second_playbook.__name__,
                    trigger_type="webhook",
                    trigger_config={},
                    enabled=True,
                ),
            ]
        )
        await session.commit()

        result = await _execute_sequence(
            ["sequence_first", "sequence_second"],
            str(alert.id),
            session_factory=db_session_factory,
        )

        assert execution_log == ["first", "second"]
        assert [item["playbook_name"] for item in result["results"]] == [
            "sequence_first",
            "sequence_second",
        ]

"""Tests for the trigger engine — matching alerts to playbooks."""
from __future__ import annotations


from opensoar.core.decorators import PlaybookMeta, RegisteredPlaybook
from opensoar.core.registry import PlaybookRegistry


class TestConditionsMatch:
    def setup_method(self):
        self.registry = PlaybookRegistry([])

    def test_empty_conditions_match_all(self):
        assert self.registry._conditions_match({}, {"severity": "high"}) is True

    def test_exact_match(self):
        assert self.registry._conditions_match({"severity": "high"}, {"severity": "high"}) is True

    def test_no_match(self):
        assert (
            self.registry._conditions_match({"severity": "high"}, {"severity": "low"}) is False
        )

    def test_list_condition(self):
        conditions = {"severity": ["high", "critical"]}
        assert self.registry._conditions_match(conditions, {"severity": "high"}) is True
        assert self.registry._conditions_match(conditions, {"severity": "critical"}) is True
        assert self.registry._conditions_match(conditions, {"severity": "low"}) is False

    def test_multiple_conditions(self):
        conditions = {"severity": "high", "source": "elastic"}
        assert (
            self.registry._conditions_match(
                conditions, {"severity": "high", "source": "elastic"}
            )
            is True
        )
        assert (
            self.registry._conditions_match(
                conditions, {"severity": "high", "source": "webhook"}
            )
            is False
        )

    def test_missing_field_no_match(self):
        assert self.registry._conditions_match({"severity": "high"}, {}) is False


class TestTriggerEngine:
    def test_match_by_source(self):
        from opensoar.core.triggers import TriggerEngine

        registry = PlaybookRegistry([])

        # Manually register a playbook
        async def my_pb(alert):
            pass

        from opensoar.core.decorators import _PLAYBOOK_REGISTRY

        _PLAYBOOK_REGISTRY["trigger_test_pb"] = RegisteredPlaybook(
            meta=PlaybookMeta(
                name="trigger_test_pb",
                trigger="webhook",
                conditions={"severity": "high"},
            ),
            func=my_pb,
            module="test",
        )

        engine = TriggerEngine(registry)
        matches = engine.match("webhook", {"severity": "high"})
        names = [m.meta.name for m in matches]
        assert "trigger_test_pb" in names

        # Clean up
        del _PLAYBOOK_REGISTRY["trigger_test_pb"]

    def test_no_match(self):
        from opensoar.core.triggers import TriggerEngine

        registry = PlaybookRegistry([])
        engine = TriggerEngine(registry)
        matches = engine.match("nonexistent_source", {"severity": "low"})
        # Should not crash, just return empty or existing matches
        assert isinstance(matches, list)

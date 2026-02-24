from __future__ import annotations

import logging

from opensoar.core.decorators import RegisteredPlaybook
from opensoar.core.registry import PlaybookRegistry

logger = logging.getLogger(__name__)


class TriggerEngine:
    def __init__(self, registry: PlaybookRegistry):
        self.registry = registry

    def match(self, source: str, alert_data: dict) -> list[RegisteredPlaybook]:
        trigger_types = [source, f"{source}.alert", "webhook"]

        matches = []
        seen = set()

        for trigger_type in trigger_types:
            for pb in self.registry.get_playbooks_for_trigger(trigger_type, alert_data):
                if pb.meta.name not in seen:
                    matches.append(pb)
                    seen.add(pb.meta.name)

        logger.info(
            f"Trigger match: source={source}, "
            f"matched {len(matches)} playbook(s): {[m.meta.name for m in matches]}"
        )
        return matches

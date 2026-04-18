from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.core.decorators import RegisteredPlaybook, get_playbook_registry
from opensoar.models.playbook import PlaybookDefinition

logger = logging.getLogger(__name__)


class PlaybookRegistry:
    def __init__(self, playbook_dirs: list[str]):
        self._playbook_dirs = playbook_dirs

    def discover(self) -> dict[str, RegisteredPlaybook]:
        for directory in self._playbook_dirs:
            dir_path = Path(directory)
            if not dir_path.exists():
                logger.warning(f"Playbook directory does not exist: {directory}")
                continue

            for py_file in sorted(dir_path.rglob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                self._import_module(py_file, dir_path)

        registry = get_playbook_registry()
        logger.info(f"Discovered {len(registry)} playbook(s)")
        for name, pb in registry.items():
            logger.info(f"  - {name} (trigger={pb.meta.trigger}, module={pb.module})")
        return registry

    def _import_module(self, py_file: Path, base_dir: Path) -> None:
        relative = py_file.relative_to(base_dir.parent)
        module_name = str(relative.with_suffix("")).replace("/", ".").replace("\\", ".")

        if module_name in sys.modules:
            return

        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                logger.debug(f"Imported playbook module: {module_name}")
        except Exception:
            logger.exception(f"Failed to import playbook module: {py_file}")

    def get_playbooks_for_trigger(
        self, trigger_type: str, alert_data: dict
    ) -> list[RegisteredPlaybook]:
        registry = get_playbook_registry()
        matches = []
        for pb in registry.values():
            if not pb.meta.enabled:
                continue
            if pb.meta.trigger != trigger_type:
                continue
            if self._conditions_match(pb.meta.conditions, alert_data):
                matches.append(pb)
        return sorted(matches, key=lambda pb: (pb.meta.order, pb.meta.name))

    def _conditions_match(self, conditions: dict, alert_data: dict) -> bool:
        if not conditions:
            return True

        for key, expected in conditions.items():
            if key not in alert_data:
                logger.warning(
                    "Trigger condition references field %r not present in alert data",
                    key,
                )
            actual = alert_data.get(key)
            if not self._condition_value_matches(expected, actual):
                return False

        return True

    def _condition_value_matches(self, expected, actual) -> bool:
        if actual is None:
            return False

        if isinstance(actual, list):
            if isinstance(expected, list):
                return any(item in expected for item in actual)
            return expected in actual

        if isinstance(expected, list):
            return actual in expected

        return actual == expected

    async def sync_to_db(self, session: AsyncSession) -> None:
        registry = get_playbook_registry()

        for name, pb in registry.items():
            result = await session.execute(
                select(PlaybookDefinition).where(PlaybookDefinition.name == name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.module_path = pb.module
                existing.function_name = pb.func.__name__
                existing.trigger_type = pb.meta.trigger
                existing.trigger_config = pb.meta.conditions
                existing.description = pb.meta.description
                existing.execution_order = pb.meta.order
            else:
                definition = PlaybookDefinition(
                    name=name,
                    description=pb.meta.description,
                    execution_order=pb.meta.order,
                    module_path=pb.module,
                    function_name=pb.func.__name__,
                    trigger_type=pb.meta.trigger,
                    trigger_config=pb.meta.conditions,
                    enabled=pb.meta.enabled,
                )
                session.add(definition)

        await session.commit()
        logger.info(f"Synced {len(registry)} playbook definition(s) to database")

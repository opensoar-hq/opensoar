"""Dynamic integration loader — discovers and registers connector classes."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class IntegrationLoader:
    """Registry of known integration connector classes.

    Discovers built-in connectors and can also load from external directories.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, type] = {}

    def discover_builtin(self) -> None:
        """Load all built-in integration connectors from opensoar.integrations.*."""
        builtins = [
            ("elastic", "opensoar.integrations.elastic.connector", "ElasticIntegration"),
            ("virustotal", "opensoar.integrations.virustotal.connector", "VirusTotalIntegration"),
            ("abuseipdb", "opensoar.integrations.abuseipdb.connector", "AbuseIPDBIntegration"),
            ("slack", "opensoar.integrations.slack.connector", "SlackIntegration"),
            ("email", "opensoar.integrations.email.connector", "EmailIntegration"),
        ]
        for type_name, module_path, class_name in builtins:
            try:
                mod = importlib.import_module(module_path)
                cls = getattr(mod, class_name)
                self._connectors[type_name] = cls
                logger.debug(f"Loaded built-in integration: {type_name}")
            except (ImportError, AttributeError) as e:
                logger.debug(f"Skipping built-in integration {type_name}: {e}")

    def discover_directory(self, directory: str) -> None:
        """Scan a directory for integration connector modules.

        Expects each subdirectory to contain a connector.py with a class
        that has an `integration_type` attribute.
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            logger.warning(f"Integration directory does not exist: {directory}")
            return

        for connector_file in sorted(dir_path.glob("*/connector.py")):
            integration_dir = connector_file.parent
            type_name = integration_dir.name

            if type_name in self._connectors:
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    f"integrations.{type_name}.connector", connector_file
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # Find the connector class (first class with integration_type attr)
                    for attr_name in dir(mod):
                        obj = getattr(mod, attr_name)
                        if (
                            isinstance(obj, type)
                            and hasattr(obj, "integration_type")
                            and obj.integration_type == type_name
                        ):
                            self._connectors[type_name] = obj
                            logger.info(f"Loaded external integration: {type_name}")
                            break
            except Exception:
                logger.exception(f"Failed to load integration from {connector_file}")

    def register(self, type_name: str, connector_cls: type) -> None:
        """Manually register a connector class."""
        self._connectors[type_name] = connector_cls

    def get_connector(self, type_name: str) -> type | None:
        """Get a connector class by integration type name."""
        return self._connectors.get(type_name)

    def available_types(self) -> list[str]:
        """Return all registered integration type names."""
        return list(self._connectors.keys())

    def available_types_detail(self) -> list[dict[str, Any]]:
        """Return all registered types with metadata."""
        result = []
        for type_name, cls in self._connectors.items():
            result.append({
                "type": type_name,
                "display_name": getattr(cls, "display_name", type_name),
                "description": getattr(cls, "description", ""),
            })
        return result

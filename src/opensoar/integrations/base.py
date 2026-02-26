from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthCheckResult:
    healthy: bool
    message: str
    details: dict[str, Any] | None = None


@dataclass
class ActionDefinition:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)


class IntegrationBase(ABC):
    integration_type: str
    display_name: str
    description: str

    def __init__(self, config: dict[str, Any]):
        self._config = config
        self._validate_config(config)

    @abstractmethod
    def _validate_config(self, config: dict[str, Any]) -> None: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def health_check(self) -> HealthCheckResult: ...

    @abstractmethod
    def get_actions(self) -> list[ActionDefinition]: ...

    async def disconnect(self) -> None:
        pass

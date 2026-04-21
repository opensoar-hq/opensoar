from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from opensoar.core.decorators import action
from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase


class SlackIntegration(IntegrationBase):
    integration_type = "slack"
    display_name = "Slack"
    description = "Send notifications and alerts to Slack channels"

    def __init__(self, config: dict[str, Any]):
        self._client: aiohttp.ClientSession | None = None
        super().__init__(config)

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "webhook_url" not in config and "bot_token" not in config:
            raise ValueError("Slack requires 'webhook_url' or 'bot_token' in config")

    async def connect(self) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if "bot_token" in self._config:
            headers["Authorization"] = f"Bearer {self._config['bot_token']}"

        self._client = aiohttp.ClientSession(headers=headers)

    async def health_check(self) -> HealthCheckResult:
        if not self._client:
            return HealthCheckResult(healthy=False, message="Not connected")

        if "bot_token" in self._config:
            try:
                async with self._client.post(
                    "https://slack.com/api/auth.test"
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return HealthCheckResult(healthy=True, message="OK")
                    return HealthCheckResult(healthy=False, message=data.get("error", "Unknown"))
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
                return HealthCheckResult(healthy=False, message=str(e))

        return HealthCheckResult(healthy=True, message="Webhook configured (cannot verify)")

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="send_message",
                description="Send a message to a Slack channel",
                parameters={
                    "channel": {"type": "string"},
                    "text": {"type": "string"},
                },
            ),
        ]

    async def send_message(self, channel: str, text: str, blocks: list | None = None) -> dict:
        if not self._client:
            raise RuntimeError("Not connected")

        if "webhook_url" in self._config:
            payload: dict[str, Any] = {"text": text}
            if blocks:
                payload["blocks"] = blocks
            async with self._client.post(self._config["webhook_url"], json=payload) as resp:
                return {"status": resp.status, "ok": resp.status == 200}

        async with self._client.post(
            "https://slack.com/api/chat.postMessage",
            json={"channel": channel, "text": text, "blocks": blocks},
        ) as resp:
            return await resp.json()

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()


@action(name="slack.send_message", timeout=15, retries=1)
async def send_message(channel: str, text: str) -> dict:
    """Send a message to Slack."""
    return {"channel": channel, "text": text, "note": "Configure Slack integration for live messages"}

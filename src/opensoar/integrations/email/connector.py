from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from opensoar.core.decorators import action
from opensoar.integrations.base import ActionDefinition, HealthCheckResult, IntegrationBase


class EmailIntegration(IntegrationBase):
    integration_type = "email"
    display_name = "Email (SMTP)"
    description = "Send email notifications via SMTP"

    def _validate_config(self, config: dict[str, Any]) -> None:
        if "smtp_host" not in config:
            raise ValueError("Email requires 'smtp_host' in config")

    async def connect(self) -> None:
        pass

    async def health_check(self) -> HealthCheckResult:
        try:
            host = self._config["smtp_host"]
            port = self._config.get("smtp_port", 587)
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                return HealthCheckResult(healthy=True, message="SMTP connection OK")
        # smtplib raises SMTPException and its subclasses for protocol-level
        # failures; OSError covers the underlying socket problems.
        except (smtplib.SMTPException, OSError, KeyError) as e:
            return HealthCheckResult(healthy=False, message=str(e))

    def get_actions(self) -> list[ActionDefinition]:
        return [
            ActionDefinition(
                name="send_email",
                description="Send an email notification",
                parameters={
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
            ),
        ]

    async def send_email(self, to: str, subject: str, body: str) -> dict:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self._config.get("from_address", "opensoar@localhost")
        msg["To"] = to
        msg.set_content(body)

        host = self._config["smtp_host"]
        port = self._config.get("smtp_port", 587)

        with smtplib.SMTP(host, port) as server:
            if self._config.get("use_tls", True):
                server.starttls()
            if "username" in self._config:
                server.login(self._config["username"], self._config["password"])
            server.send_message(msg)

        return {"sent_to": to, "subject": subject}


@action(name="email.send", timeout=30, retries=1)
async def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email notification."""
    return {"to": to, "subject": subject, "note": "Configure Email integration for live sending"}

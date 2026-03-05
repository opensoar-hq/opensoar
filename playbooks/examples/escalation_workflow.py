"""Playbook: Escalation workflow for critical alerts.

Triggers on critical-severity alerts. Automatically assigns to the first
available admin analyst, logs escalation activity, and sends a Slack
notification if configured.
"""

import logging

from opensoar import action, playbook

logger = logging.getLogger(__name__)


@action(name="find_duty_analyst", timeout=10)
async def find_duty_analyst() -> dict:
    """Find an active admin analyst to assign the alert to."""
    from sqlalchemy import select

    from opensoar.db import async_session
    from opensoar.models.analyst import Analyst

    async with async_session() as session:
        result = await session.execute(
            select(Analyst)
            .where(Analyst.is_active.is_(True), Analyst.role == "admin")
            .order_by(Analyst.username)
            .limit(1)
        )
        analyst = result.scalar_one_or_none()
        if analyst:
            return {
                "found": True,
                "analyst_id": str(analyst.id),
                "username": analyst.username,
                "display_name": analyst.display_name,
            }
        return {"found": False, "note": "No admin analysts available"}


@action(name="assign_alert", timeout=10)
async def assign_alert(alert_id: str, analyst_id: str, analyst_username: str) -> dict:
    """Assign an alert to a specific analyst."""
    import uuid

    from sqlalchemy import select

    from opensoar.db import async_session
    from opensoar.models.activity import Activity
    from opensoar.models.alert import Alert

    async with async_session() as session:
        result = await session.execute(
            select(Alert).where(Alert.id == uuid.UUID(alert_id))
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return {"assigned": False, "error": "Alert not found"}

        alert.assigned_to = uuid.UUID(analyst_id)
        alert.assigned_username = analyst_username
        if alert.status == "new":
            alert.status = "in_progress"

        session.add(Activity(
            alert_id=alert.id,
            action="assigned",
            detail=f"Auto-escalated and assigned to {analyst_username}",
            metadata_json={"auto_escalated": True},
        ))

        await session.commit()
        return {"assigned": True, "to": analyst_username}


@action(name="send_escalation_notification", timeout=15, retries=1)
async def send_escalation_notification(alert_title: str, severity: str, assignee: str) -> dict:
    """Send escalation notification via Slack (if configured)."""
    try:
        from opensoar.config import settings
        from opensoar.integrations.slack.connector import SlackConnector

        # Check if Slack integration is available in DB
        from sqlalchemy import select

        from opensoar.db import async_session
        from opensoar.models.integration import IntegrationInstance

        async with async_session() as session:
            result = await session.execute(
                select(IntegrationInstance).where(
                    IntegrationInstance.integration_type == "slack",
                    IntegrationInstance.enabled.is_(True),
                )
            )
            slack_config = result.scalar_one_or_none()

        if slack_config and slack_config.config.get("webhook_url"):
            slack = SlackConnector(slack_config.config)
            await slack.connect()
            try:
                await slack.send_message(
                    channel=slack_config.config.get("default_channel", "#soc-alerts"),
                    text=f"*CRITICAL ALERT ESCALATED*\n"
                    f"*Title:* {alert_title}\n"
                    f"*Severity:* {severity}\n"
                    f"*Assigned to:* {assignee}",
                )
                return {"notified": True, "channel": slack_config.config.get("default_channel")}
            finally:
                await slack.disconnect()
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Slack notification failed: {e}")

    logger.info(f"Escalation: [{severity}] {alert_title} -> {assignee}")
    return {"notified": False, "note": "Slack not configured, logged only"}


@playbook(
    trigger="webhook",
    conditions={"severity": ["critical"]},
    description="Auto-escalate critical alerts: assign to duty analyst and notify SOC",
)
async def escalation_workflow(alert_data):
    """Escalation workflow for critical severity alerts."""
    if hasattr(alert_data, "id"):
        alert_id = str(alert_data.id)
        title = alert_data.title
        severity = alert_data.severity
    elif isinstance(alert_data, dict):
        alert_id = alert_data.get("id", "")
        title = alert_data.get("title", "Unknown")
        severity = alert_data.get("severity", "critical")
    else:
        return {"escalated": False, "error": "Invalid alert data"}

    # Find duty analyst
    duty = await find_duty_analyst()
    if not duty.get("found"):
        return {"escalated": False, "note": "No admin analyst available for assignment"}

    # Assign alert
    assignment = await assign_alert(
        alert_id=alert_id,
        analyst_id=duty["analyst_id"],
        analyst_username=duty["username"],
    )

    # Notify
    notification = await send_escalation_notification(
        alert_title=title,
        severity=severity,
        assignee=duty["display_name"],
    )

    return {
        "escalated": True,
        "assigned_to": duty["display_name"],
        "assignment": assignment,
        "notification": notification,
    }

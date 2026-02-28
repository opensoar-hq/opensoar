from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.ingestion.webhook import process_webhook
from opensoar.schemas.webhook import WebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/alerts", response_model=WebhookResponse)
async def receive_alert(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    alert = await process_webhook(session, payload, source="webhook")

    from opensoar.main import get_trigger_engine

    engine = get_trigger_engine()
    matches = engine.match(alert.source, alert.normalized)

    playbook_names = []
    for pb in matches:
        from opensoar.worker.tasks import execute_playbook_task

        execute_playbook_task.delay(pb.meta.name, str(alert.id))
        playbook_names.append(pb.meta.name)

    await session.commit()

    return WebhookResponse(
        alert_id=alert.id,
        title=alert.title,
        severity=alert.severity,
        playbooks_triggered=playbook_names,
        message=f"Alert ingested. {len(playbook_names)} playbook(s) triggered.",
    )


@router.post("/alerts/elastic", response_model=WebhookResponse)
async def receive_elastic_alert(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    alert = await process_webhook(session, payload, source="elastic")

    from opensoar.main import get_trigger_engine

    engine = get_trigger_engine()
    matches = engine.match("elastic", alert.normalized)

    playbook_names = []
    for pb in matches:
        from opensoar.worker.tasks import execute_playbook_task

        execute_playbook_task.delay(pb.meta.name, str(alert.id))
        playbook_names.append(pb.meta.name)

    await session.commit()

    return WebhookResponse(
        alert_id=alert.id,
        title=alert.title,
        severity=alert.severity,
        playbooks_triggered=playbook_names,
        message=f"Elastic alert ingested. {len(playbook_names)} playbook(s) triggered.",
    )

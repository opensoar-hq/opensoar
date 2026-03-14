from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.api_key import hash_api_key
from opensoar.ingestion.webhook import process_webhook
from opensoar.models.api_key import ApiKey
from opensoar.schemas.webhook import WebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _validate_webhook_key(
    session: AsyncSession = Depends(get_db),
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Validate the API key if one is provided.

    - If no key is sent and no keys exist in the DB → open mode (allow).
    - If no key is sent but keys exist → still allow (backward compat, will tighten later).
    - If a key is sent → it must be valid and active, otherwise 401.
    """
    if api_key is None:
        return

    key_hash = hash_api_key(api_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    db_key = result.scalar_one_or_none()
    if db_key is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Update last_used_at
    db_key.last_used_at = datetime.now(timezone.utc)
    await session.commit()


@router.post("/alerts", response_model=WebhookResponse)
async def receive_alert(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
    _key: None = Depends(_validate_webhook_key),
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
    _key: None = Depends(_validate_webhook_key),
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

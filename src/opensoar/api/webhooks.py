from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.api.deps import get_db
from opensoar.auth.api_key import hash_api_key
from opensoar.ingestion.webhook import process_webhook
from opensoar.models.api_key import ApiKey
from opensoar.plugins import dispatch_api_key_validators
from opensoar.schemas.webhook import WebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_hmac_signature(body: bytes, secret: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature of request body."""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature[7:])


async def _validate_webhook_key(
    request: Request,
    session: AsyncSession = Depends(get_db),
    api_key: str | None = Security(_api_key_header),
    x_webhook_signature: str | None = Header(None),
    required_scope: str = "webhooks:ingest",
) -> None:
    """Validate the API key and optional HMAC signature.

    - If no key is sent and no keys exist in the DB → open mode (allow).
    - If no key is sent but keys exist → still allow (backward compat, will tighten later).
    - If a key is sent → it must be valid, active, and not expired, otherwise 401.
    - If X-Webhook-Signature is sent → verify HMAC-SHA256 of the body using the API key.
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

    # Check expiry
    if db_key.expires_at is not None and db_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    # Verify HMAC signature if provided
    if x_webhook_signature is not None:
        body = await request.body()
        if not _verify_hmac_signature(body, api_key, x_webhook_signature):
            raise HTTPException(
                status_code=401, detail="Invalid webhook signature"
            )

    # Update last_used_at
    db_key.last_used_at = datetime.now(timezone.utc)
    await dispatch_api_key_validators(
        request.app,
        api_key=db_key,
        request=request,
        required_scope=required_scope,
    )
    await session.commit()


async def _validate_default_webhook_key(
    request: Request,
    session: AsyncSession = Depends(get_db),
    api_key: str | None = Security(_api_key_header),
    x_webhook_signature: str | None = Header(None),
) -> None:
    await _validate_webhook_key(
        request,
        session=session,
        api_key=api_key,
        x_webhook_signature=x_webhook_signature,
        required_scope="webhooks:ingest",
    )


async def _validate_elastic_webhook_key(
    request: Request,
    session: AsyncSession = Depends(get_db),
    api_key: str | None = Security(_api_key_header),
    x_webhook_signature: str | None = Header(None),
) -> None:
    await _validate_webhook_key(
        request,
        session=session,
        api_key=api_key,
        x_webhook_signature=x_webhook_signature,
        required_scope="webhooks:ingest:elastic",
    )


@router.post("/alerts", response_model=WebhookResponse)
async def receive_alert(
    payload: dict[str, Any],
    session: AsyncSession = Depends(get_db),
    _key: None = Depends(_validate_default_webhook_key),
):
    alert = await process_webhook(session, payload, source="webhook")

    from opensoar.main import get_trigger_engine

    engine = get_trigger_engine()
    matches = engine.match(alert.source, alert.normalized)

    playbook_names = []
    if matches:
        from opensoar.worker.tasks import execute_playbook_sequence_task

        playbook_names = [pb.meta.name for pb in matches]
        execute_playbook_sequence_task.delay(playbook_names, str(alert.id))

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
    _key: None = Depends(_validate_elastic_webhook_key),
):
    alert = await process_webhook(session, payload, source="elastic")

    from opensoar.main import get_trigger_engine

    engine = get_trigger_engine()
    matches = engine.match("elastic", alert.normalized)

    playbook_names = []
    if matches:
        from opensoar.worker.tasks import execute_playbook_sequence_task

        playbook_names = [pb.meta.name for pb in matches]
        execute_playbook_sequence_task.delay(playbook_names, str(alert.id))

    await session.commit()

    return WebhookResponse(
        alert_id=alert.id,
        title=alert.title,
        severity=alert.severity,
        playbooks_triggered=playbook_names,
        message=f"Elastic alert ingested. {len(playbook_names)} playbook(s) triggered.",
    )

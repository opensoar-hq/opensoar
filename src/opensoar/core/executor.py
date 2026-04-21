from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.core.decorators import (
    ExecutionContext,
    RegisteredPlaybook,
    set_execution_context,
)
from opensoar.logging_context import (
    correlation_id_ctx,
    generate_correlation_id,
)
from opensoar.middleware.metrics import record_playbook_run
from opensoar.models.action_result import ActionResult
from opensoar.models.alert import Alert
from opensoar.models.playbook import PlaybookDefinition
from opensoar.models.playbook_run import PlaybookRun

logger = logging.getLogger(__name__)


class PlaybookExecutor:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(
        self,
        playbook: RegisteredPlaybook,
        alert_id: uuid.UUID | None = None,
        manual_input: dict | None = None,
        sequence_id: uuid.UUID | None = None,
        sequence_position: int | None = None,
        sequence_total: int | None = None,
    ) -> PlaybookRun:
        pb_def = await self.session.execute(
            select(PlaybookDefinition).where(PlaybookDefinition.name == playbook.meta.name)
        )
        pb_row = pb_def.scalar_one_or_none()
        if not pb_row:
            raise ValueError(f"Playbook '{playbook.meta.name}' not found in database")

        # Resolve the correlation id BEFORE creating the run so the value
        # sticks to the row.  Prefer (in order): the triggering alert's id,
        # an already-set contextvar (e.g. from a sequence runner), or a
        # freshly minted one for manual invocations.  This makes run.id
        # distinct from correlation_id: runs are 1 per playbook, correlation
        # ids are 1 per originating alert and span every run for it.
        alert = None
        if alert_id:
            result = await self.session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = result.scalar_one_or_none()

        correlation_id = (
            (alert.correlation_id if alert and alert.correlation_id else None)
            or correlation_id_ctx.get()
            or generate_correlation_id()
        )

        run = PlaybookRun(
            playbook_id=pb_row.id,
            alert_id=alert_id,
            sequence_id=sequence_id,
            sequence_position=sequence_position,
            sequence_total=sequence_total,
            status="running",
            started_at=datetime.now(timezone.utc),
            correlation_id=correlation_id,
        )
        self.session.add(run)
        await self.session.flush()

        async def record_action(**kwargs: Any) -> None:
            started = kwargs.get("started_at", datetime.now(timezone.utc))
            finished = kwargs.get("finished_at", datetime.now(timezone.utc))
            duration_ms = int((finished - started).total_seconds() * 1000)

            action_result = ActionResult(
                run_id=run.id,
                action_name=kwargs["action_name"],
                status=kwargs["status"],
                started_at=started,
                finished_at=finished,
                duration_ms=duration_ms,
                output_data=kwargs.get("output_data"),
                error=kwargs.get("error"),
                attempt=kwargs.get("attempt", 1),
                correlation_id=correlation_id,
            )
            self.session.add(action_result)
            await self.session.flush()

        ctx = ExecutionContext(
            run_id=run.id,
            alert_id=alert_id,
            session=self.session,
            record_action=record_action,
            correlation_id=correlation_id,
        )
        set_execution_context(ctx)
        cid_token = correlation_id_ctx.set(correlation_id)

        try:
            input_data = alert or manual_input or {}
            result = await playbook.func(input_data)

            run.status = "success"
            run.result = result if isinstance(result, dict) else {"result": result}
            logger.info(
                f"Playbook '{playbook.meta.name}' completed successfully "
                f"(run={run.id}, correlation_id={correlation_id})"
            )

        except asyncio.CancelledError:
            run.status = "cancelled"
            logger.warning(
                f"Playbook '{playbook.meta.name}' was cancelled "
                f"(run={run.id}, correlation_id={correlation_id})"
            )

        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            logger.exception(
                f"Playbook '{playbook.meta.name}' failed "
                f"(run={run.id}, correlation_id={correlation_id})"
            )

        finally:
            set_execution_context(None)
            correlation_id_ctx.reset(cid_token)
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()

            started = run.started_at or run.finished_at
            duration = (run.finished_at - started).total_seconds()
            record_playbook_run(
                playbook_name=playbook.meta.name,
                status=run.status,
                duration_seconds=max(duration, 0.0),
            )

        return run

"""Resolve parsed mention tokens against the current tenant's analyst list.

The resolver delegates tenant filtering to the optional
``tenant_access_validators`` plugin surface so a cross-tenant mention is
treated exactly like a username that does not exist (silently dropped).
The caller can then store only the validated usernames and dispatch
notifications to those analysts.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.models.analyst import Analyst
from opensoar.plugins import enforce_tenant_access


@dataclass(frozen=True)
class ResolvedMention:
    username: str
    analyst_id: uuid.UUID


async def resolve_mentions(
    *,
    app: FastAPI,
    session: AsyncSession,
    usernames: list[str],
    analyst: Analyst | None,
    request,
) -> list[ResolvedMention]:
    """Return the subset of ``usernames`` that the caller may mention.

    - Usernames matched case-insensitively against ``analysts.username``.
    - Inactive analysts are skipped.
    - Analysts outside the caller's tenant are skipped (a tenant plugin can
      raise ``HTTPException`` from :func:`enforce_tenant_access`; we treat that
      as "invisible" and simply drop the token rather than error the comment).
    - Duplicates are collapsed; output order matches the input order.
    """
    if not usernames:
        return []

    lowered = [u.lower() for u in usernames]
    result = await session.execute(
        select(Analyst).where(
            func.lower(Analyst.username).in_(lowered),
            Analyst.is_active.is_(True),
        )
    )
    found = {a.username.lower(): a for a in result.scalars().all()}

    resolved: list[ResolvedMention] = []
    seen: set[str] = set()
    for token in lowered:
        if token in seen:
            continue
        seen.add(token)
        target = found.get(token)
        if target is None:
            continue
        try:
            await enforce_tenant_access(
                app,
                resource=target,
                resource_type="analyst",
                action="mention",
                analyst=analyst,
                request=request,
                session=session,
            )
        except HTTPException:
            # Mention crosses a tenant boundary — silently drop.
            continue
        resolved.append(
            ResolvedMention(username=target.username.lower(), analyst_id=target.id)
        )
    return resolved

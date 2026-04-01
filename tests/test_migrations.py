"""Verify Alembic migrations stay in sync with SQLAlchemy models.

This test catches the class of bug where a model is added/changed but the
corresponding migration is missing — exactly what caused the 'relation
incidents does not exist' production error.
"""
from __future__ import annotations

import os
import subprocess

import pytest


@pytest.mark.asyncio
async def test_migrations_are_in_sync_with_models(db_engine):
    """After applying all migrations, alembic check should detect no drift."""
    project_root = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        ["alembic", "check"],
        cwd=project_root,
        env={
            **os.environ,
            "DATABASE_URL": os.environ.get(
                "DATABASE_URL",
                "postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar_test",
            ),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Alembic detected model/migration drift. "
        f"Run 'alembic revision --autogenerate' to fix.\n"
        f"{result.stdout}\n{result.stderr}"
    )

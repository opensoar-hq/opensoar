from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from opensoar.bootstrap_admin import bootstrap_local_admin


class TestBootstrapAdmin:
    async def test_bootstrap_creates_first_active_admin(self, db_session_factory):
        async with db_session_factory() as session:
            from opensoar.models.analyst import Analyst

            existing_admins = await session.execute(select(Analyst).where(Analyst.role == "admin"))
            for existing in existing_admins.scalars():
                existing.is_active = False
            await session.commit()

        analyst = await bootstrap_local_admin(
            username=f"bootstrap_{uuid.uuid4().hex[:8]}",
            password="securepass123",
            display_name="Bootstrap Admin",
            email="bootstrap@opensoar.app",
            session_factory=db_session_factory,
        )

        assert analyst.role == "admin"
        assert analyst.is_active is True
        assert analyst.password_hash is not None

    async def test_bootstrap_rejects_when_active_admin_exists(self, session, db_session_factory):
        from opensoar.api.auth import _hash_password
        from opensoar.models.analyst import Analyst

        session.add(
            Analyst(
                username=f"existing_{uuid.uuid4().hex[:8]}",
                display_name="Existing Admin",
                email="existing@opensoar.app",
                password_hash=_hash_password("securepass123"),
                role="admin",
                is_active=True,
            )
        )
        await session.commit()

        with pytest.raises(RuntimeError, match="active admin already exists"):
            await bootstrap_local_admin(
                username=f"blocked_{uuid.uuid4().hex[:8]}",
                password="securepass123",
                session_factory=db_session_factory,
            )

    async def test_bootstrap_rejects_duplicate_username(self, session, db_session_factory):
        from opensoar.api.auth import _hash_password
        from opensoar.models.analyst import Analyst

        existing_admins = await session.execute(select(Analyst).where(Analyst.role == "admin"))
        for existing in existing_admins.scalars():
            existing.is_active = False

        username = f"duplicate_{uuid.uuid4().hex[:8]}"
        session.add(
            Analyst(
                username=username,
                display_name="Duplicate User",
                email="duplicate@opensoar.app",
                password_hash=_hash_password("securepass123"),
                role="analyst",
                is_active=True,
            )
        )
        await session.commit()

        with pytest.raises(RuntimeError, match="already taken"):
            await bootstrap_local_admin(
                username=username,
                password="securepass123",
                session_factory=db_session_factory,
            )

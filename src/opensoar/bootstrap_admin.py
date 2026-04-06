from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opensoar.db import async_session
from opensoar.models.analyst import Analyst


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def bootstrap_local_admin(
    *,
    username: str,
    password: str,
    display_name: str | None = None,
    email: str | None = None,
    session_factory: Callable[[], AsyncSession] = async_session,
) -> Analyst:
    async with session_factory() as session:
        existing_admin = await session.execute(
            select(Analyst.id).where(
                Analyst.role == "admin",
                Analyst.is_active.is_(True),
            )
        )
        if existing_admin.first() is not None:
            raise RuntimeError("An active admin already exists; use the admin account-management flow instead.")

        existing_user = await session.execute(
            select(Analyst.id).where(Analyst.username == username)
        )
        if existing_user.first() is not None:
            raise RuntimeError(f"Username '{username}' is already taken.")

        analyst = Analyst(
            username=username,
            display_name=display_name or username,
            email=email,
            password_hash=_hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(analyst)
        await session.commit()
        await session.refresh(analyst)
        return analyst


async def _async_main(args: argparse.Namespace) -> int:
    try:
        analyst = await bootstrap_local_admin(
            username=args.username,
            password=args.password,
            display_name=args.display_name,
            email=args.email,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created admin '{analyst.username}'.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the first local OpenSOAR admin")
    parser.add_argument("--username", required=True, help="Username for the new admin")
    parser.add_argument("--password", required=True, help="Password for the new admin")
    parser.add_argument("--display-name", help="Display name for the new admin")
    parser.add_argument("--email", help="Email address for the new admin")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()

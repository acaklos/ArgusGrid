"""DEVELOPMENT ONLY: loginless mode (rules/20).

Physically removed from deploy and publish packages (DEV-005). It only works when ARGUS_ENV=development,
ARGUS_DEV_LOGINLESS=1 and the application is bound to the loopback address (see core/config.py).
It acts as a fixed ordinary user of a chosen role. It is not the Emergency Owner and does not bypass RBAC.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from sqlalchemy import select

from app.core.context import Actor
from app.models.identity import Role, User

if TYPE_CHECKING:  # pragma: no cover
    from app.services.container import Services

BANNER = "LOGINLESS DEV MODE"  # DEV-004 (the publish scan looks for this string)
FLAG_NAME = "ARGUS_DEV_LOGINLESS"  # DEV-006 (the publish scan looks for this name)


def read_flag(environ: Any, environment: str) -> tuple[bool, str]:
    """(active, role). The flag only counts in development mode; anywhere else it is ignored (DEV-001, DEV-007)."""
    active = str(environ.get(FLAG_NAME, "0")).strip() == "1" and environment == "development"
    return active, str(environ.get(FLAG_NAME + "_ROLE", "Administrator")).strip()


def principal_for(svc: "Services", principal_cls: Any) -> Any | None:
    user = svc.session.execute(
        select(User).join(Role, User.role_id == Role.id)
        .where(Role.name == svc.config.dev_loginless_role, User.is_active.is_(True))
        .order_by(User.id).limit(1)
    ).scalar_one_or_none()
    if user is None:
        return None
    actor = Actor(kind="user", name=user.username, role=user.role.name, user_id=user.id)
    return principal_cls(actor=actor, user=user, session=None, capabilities=frozenset(user.role.capabilities),
                         dev_loginless=True)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def banner_header(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Argus-Dev-Mode"] = BANNER
        return response

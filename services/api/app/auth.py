from __future__ import annotations

from dataclasses import dataclass
import logging

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_db
from .models import Membership, User
from .observability import bind_request_context, get_logger, log_event


logger = get_logger("auth")


@dataclass(frozen=True)
class RequestContext:
    user: User
    membership: Membership

    @property
    def user_id(self) -> str:
        return self.user.id

    @property
    def organization_id(self) -> str:
        return self.membership.organization_id

    @property
    def role(self) -> str:
        return self.membership.role


@dataclass(frozen=True)
class AuthIdentity:
    uid: str
    email: str | None
    email_verified: bool
    display_name: str | None = None


async def _firebase_identity(authorization: str | None) -> AuthIdentity:
    if not authorization or not authorization.startswith("Bearer "):
        log_event(logger, logging.WARNING, "auth.missing_bearer_token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth

        if not firebase_admin._apps:
            options = {"projectId": get_settings().firebase_project_id} if get_settings().firebase_project_id else None
            firebase_admin.initialize_app(options=options)
        decoded = firebase_auth.verify_id_token(authorization.removeprefix("Bearer "))
        email = decoded.get("email")
        return AuthIdentity(
            uid=str(decoded["uid"]),
            email=str(email).strip().lower() if email else None,
            email_verified=bool(decoded.get("email_verified")),
            display_name=str(decoded["name"]).strip() if decoded.get("name") else None,
        )
    except Exception as exc:
        log_event(logger, logging.WARNING, "auth.invalid_identity_token", error_type=type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity token") from exc


async def get_auth_identity(
    request: Request,
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> AuthIdentity:
    settings = get_settings()
    identity = (
        AuthIdentity(uid=x_user_id or "user-ayman", email=None, email_verified=True)
        if settings.auth_mode == "development"
        else await _firebase_identity(authorization)
    )
    request.state.auth_identity = identity
    request.state.email_verified = identity.email_verified
    return identity


async def get_identity_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    identity: AuthIdentity = Depends(get_auth_identity),
) -> User:
    settings = get_settings()
    if settings.auth_mode == "development":
        user_filter = User.id == identity.uid
    else:
        user_filter = User.firebase_uid == identity.uid

    user = await db.scalar(select(User).where(user_filter, User.display_name != "Deleted user"))
    if not user:
        log_event(logger, logging.WARNING, "auth.user_not_provisioned")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not provisioned")
    request.state.user_id = user.id
    bind_request_context(user_id=user.id)
    return user


async def require_verified_user(
    user: User = Depends(get_identity_user),
    identity: AuthIdentity = Depends(get_auth_identity),
) -> User:
    if not identity.email_verified:
        log_event(logger, logging.WARNING, "auth.email_not_verified")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verify your email before continuing")
    return user


async def get_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_verified_user),
    x_organization_id: str | None = Header(default=None),
) -> RequestContext:

    membership_query = select(Membership).where(Membership.user_id == user.id, Membership.active.is_(True))
    if x_organization_id:
        membership_query = membership_query.where(Membership.organization_id == x_organization_id)
    membership = await db.scalar(membership_query.order_by(Membership.created_at))
    if not membership:
        log_event(logger, logging.WARNING, "auth.membership_denied")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization membership")
    request.state.organization_id = membership.organization_id
    bind_request_context(organization_id=membership.organization_id)
    return RequestContext(user=user, membership=membership)


def require_role(*allowed: str):
    async def dependency(context: RequestContext = Depends(get_context)) -> RequestContext:
        if context.role not in allowed:
            log_event(logger, logging.WARNING, "auth.role_denied", role=context.role, allowed_roles=list(allowed))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient organization role")
        return context

    return dependency

"""Password hashing (Argon2), JWT creation/validation and role-based access dependencies."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import get_db
from app.models import User, UserRole

password_hasher = PasswordHash.recommended()  # Argon2id with library-recommended parameters
# Verified against when the user does not exist, so response time doesn't reveal valid accounts.
_DUMMY_HASH = password_hasher.hash("timing-equaliser-not-a-real-password")

_bearer = HTTPBearer(auto_error=False, description="JWT from POST /api/auth/login")

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated or token is invalid/expired.",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        password_hasher.verify(password, _DUMMY_HASH)
        return False
    try:
        return password_hasher.verify(password, hashed)
    except Exception:  # malformed hash in DB: treat as a failed login, never a 500
        return False


def create_access_token(user: User, *, expires_delta: timedelta | None = None) -> tuple[str, int]:
    """Return (token, lifetime_seconds). Claims: sub=user id, role, iat, exp."""
    settings = get_settings()
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    claims = {"sub": str(user.id), "role": user.role.value, "iat": now, "exp": now + lifetime}
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # pinned: rejects alg=none and algorithm swaps
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.PyJWTError:
        raise _UNAUTHENTICATED from None


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Accept `Authorization: Bearer <jwt>` or the httpOnly auth cookie."""
    token = credentials.credentials if credentials else request.cookies.get(get_settings().auth_cookie_name)
    if not token:
        raise _UNAUTHENTICATED
    claims = _decode(token)
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError):
        raise _UNAUTHENTICATED from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHENTICATED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory: 403 unless the current user has one of `roles`."""

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action.")
        return user

    return checker


StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY))]

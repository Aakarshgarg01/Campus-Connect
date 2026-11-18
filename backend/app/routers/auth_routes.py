"""/api/auth: register, login (rate limited), logout, current user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import limiter, login_limit
from app.core.security import CurrentUser, create_access_token
from app.database.connection import get_db
from app.schemas.user_schema import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

DB = Annotated[Session, Depends(get_db)]


def _set_auth_cookie(response: Response, token: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        max_age=max_age,
        httponly=True,  # not readable by JavaScript
        secure=settings.cookies_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Student self-registration")
def register(data: RegisterRequest, db: DB) -> UserOut:
    return auth_service.to_user_out(auth_service.register_student(db, data))


@router.post("/login", response_model=TokenResponse, summary="Log in; returns a JWT and sets an httpOnly cookie")
@limiter.limit(login_limit)
def login(request: Request, response: Response, data: LoginRequest, db: DB) -> TokenResponse:
    user = auth_service.authenticate(db, data.identifier, data.password)
    if user is None:
        # One message for unknown user and wrong password: don't reveal which accounts exist.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials.")
    token, expires_in = create_access_token(user)
    _set_auth_cookie(response, token, expires_in)
    return TokenResponse(access_token=token, expires_in=expires_in, user=auth_service.to_user_out(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Clear the auth cookie")
def logout(response: Response) -> Response:
    settings = get_settings()
    response.delete_cookie(
        settings.auth_cookie_name, path="/", httponly=True,
        secure=settings.cookies_secure, samesite=settings.cookie_samesite,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut, summary="The signed-in user")
def me(user: CurrentUser) -> UserOut:
    return auth_service.to_user_out(user)

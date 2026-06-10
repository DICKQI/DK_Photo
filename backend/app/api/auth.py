from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlmodel import select

from app.deps import CurrentUser, SessionDep
from app.models import User
from app.schemas import LoginRequest, UserRead
from app.security import create_access_token, verify_password
from app.services.operation_log import log_operation


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
def login(payload: LoginRequest, response: Response, session: SessionDep) -> User:
    user = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if not user or not verify_password(payload.password, user.password_hash):
        log_operation(
            "auth.login",
            category="audit",
            status="failure",
            target_type="user",
            target_id=payload.email.lower(),
            message="Login failed",
            metadata={"email": payload.email.lower()},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active or user.deleted_at:
        log_operation(
            "auth.login",
            category="audit",
            status="failure",
            target_type="user",
            target_id=str(user.id or ""),
            message="Inactive user login blocked",
            metadata={"email": user.email},
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    token = create_access_token(str(user.id), user.role, user.token_version)
    response.set_cookie(
        "dk_photo_token",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
    )
    log_operation(
        "auth.login",
        category="audit",
        status="success",
        actor_id=user.id,
        target_type="user",
        target_id=str(user.id or ""),
        message="Login succeeded",
        metadata={"email": user.email},
    )
    return user


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> User:
    return current_user


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("dk_photo_token")
    log_operation("auth.logout", category="audit", status="success", message="Logout requested")
    return {"ok": True}

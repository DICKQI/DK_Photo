from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from sqlmodel import select

from app.deps import AdminUser, SessionDep
from app.models import LibraryPermission, LibraryRoot, ScanJob, ShareLink, User
from app.schemas import (
    FilesystemChildren,
    FilesystemRoots,
    LibraryCreate,
    LibraryPermissionRead,
    LibraryPermissionUpdate,
    LibraryRead,
    PasswordReset,
    ScanJobRead,
    ShareRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.security import hash_password
from app.services.filesystem import list_children, list_roots
from app.services.paths import resolve_library_path
from app.services.scanner import run_scan_job


router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/libraries", response_model=list[LibraryRead])
def list_libraries(session: SessionDep, _: AdminUser) -> list[LibraryRoot]:
    return session.exec(select(LibraryRoot).order_by(LibraryRoot.name)).all()


@router.get("/filesystem/roots", response_model=FilesystemRoots)
def filesystem_roots(_: AdminUser) -> FilesystemRoots:
    return list_roots()


@router.get("/filesystem/children", response_model=FilesystemChildren)
def filesystem_children(path: str, _: AdminUser) -> FilesystemChildren:
    return list_children(path)


@router.post("/libraries", response_model=LibraryRead)
def create_library(payload: LibraryCreate, request: Request, session: SessionDep, _: AdminUser) -> LibraryRoot:
    path = resolve_library_path(payload.path)
    existing = session.exec(select(LibraryRoot).where(LibraryRoot.path == str(path))).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Library already exists")
    library = LibraryRoot(name=payload.name, path=str(path), is_enabled=True)
    session.add(library)
    session.commit()
    session.refresh(library)
    watcher = getattr(request.app.state, "library_watcher", None)
    if watcher:
        watcher.refresh()
    return library


@router.post("/libraries/{library_id}/scan", response_model=ScanJobRead)
def scan_library_endpoint(
    library_id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _: AdminUser,
) -> ScanJob:
    library = session.get(LibraryRoot, library_id)
    if not library:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    if not Path(library.path).exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Library path does not exist")
    job = ScanJob(library_id=library_id, status="queued", message="Manual scan queued")
    session.add(job)
    session.commit()
    session.refresh(job)
    background_tasks.add_task(_run_job_in_new_session, job.id or 0)
    return job


def _run_job_in_new_session(job_id: int) -> None:
    from sqlmodel import Session

    from app.db import engine

    with Session(engine) as session:
        run_scan_job(session, job_id)


@router.get("/jobs", response_model=list[ScanJobRead])
def list_jobs(session: SessionDep, _: AdminUser) -> list[ScanJob]:
    return session.exec(select(ScanJob).order_by(ScanJob.id.desc()).limit(40)).all()


@router.get("/users", response_model=list[UserRead])
def list_users(session: SessionDep, _: AdminUser) -> list[User]:
    return session.exec(select(User).order_by(User.created_at.desc())).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("/users", response_model=UserRead)
def create_user(payload: UserCreate, session: SessionDep, _: AdminUser) -> User:
    role = payload.role if payload.role in {"admin", "member"} else "member"
    existing = session.exec(select(User).where(User.email == payload.email.lower())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        role=role,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.email and payload.email.lower() != user.email:
        existing = session.exec(select(User).where(User.email == payload.email.lower(), User.id != user_id)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        user.email = payload.email.lower()
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        user.role = payload.role if payload.role in {"admin", "member"} else user.role
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/password")
def reset_user_password(user_id: int, payload: PasswordReset, session: SessionDep, _: AdminUser) -> dict[str, bool]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(payload.password)
    session.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disable", response_model=UserRead)
def disable_user(user_id: int, session: SessionDep, admin: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable your own account")
    user.is_active = False
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/enable", response_model=UserRead)
def enable_user(user_id: int, session: SessionDep, _: AdminUser) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    session.commit()
    session.refresh(user)
    return user


@router.get("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def get_user_permissions(user_id: int, session: SessionDep, _: AdminUser) -> list[LibraryPermission]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.put("/users/{user_id}/permissions", response_model=list[LibraryPermissionRead])
def update_user_permissions(
    user_id: int,
    payload: list[LibraryPermissionUpdate],
    session: SessionDep,
    _: AdminUser,
) -> list[LibraryPermission]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    existing = session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()
    by_library = {item.library_id: item for item in existing}
    seen_library_ids: set[int] = set()

    for item in payload:
        library = session.get(LibraryRoot, item.library_id)
        if not library:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Library {item.library_id} not found")
        seen_library_ids.add(item.library_id)
        permission = by_library.get(item.library_id)
        if item.can_view:
            if permission:
                permission.can_view = True
                permission.can_share = item.can_share
            else:
                session.add(
                    LibraryPermission(
                        user_id=user_id,
                        library_id=item.library_id,
                        can_view=True,
                        can_share=item.can_share,
                    )
                )
        elif permission:
            session.delete(permission)

    for permission in existing:
        if permission.library_id not in seen_library_ids:
            session.delete(permission)

    session.commit()
    return session.exec(select(LibraryPermission).where(LibraryPermission.user_id == user_id)).all()


@router.get("/shares", response_model=list[ShareRead])
def list_shares(session: SessionDep, _: AdminUser) -> list[ShareLink]:
    return session.exec(select(ShareLink).order_by(ShareLink.created_at.desc())).all()

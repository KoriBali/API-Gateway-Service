from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    CurrentUser,
    get_current_user,
    require_roles,
    verify_password,
)
from app.utils.response import success_response, to_json
from app.modules.identity import permissions
from app.modules.identity.repository import UserRepository, AuthRepository
from app.modules.identity.schemas import (
    UserCreate,
    UserUpdate,
    PasswordChangeRequest,
    PasswordResetRequest,
    UserRead,
)

routerUsers = APIRouter(prefix="/api/users", tags=["Users"])



# ===== Self User Endpoint =====
@routerUsers.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    user = await UserRepository.get_by_id(db, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return success_response(data=to_json(UserRead.model_validate(user)), to_camel=False, message="Current user")


@routerUsers.post("/me/password")
async def change_my_password(
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    user = await UserRepository.get_by_id(db, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is incorrect")
    await UserRepository.set_password(db, user, payload.new_password)
    await AuthRepository.revoke_all_for_user(db, user.id)
    return success_response(data={"changed": True}, message="Password changed")



# ===== Management User Endpoint =====
@routerUsers.post("")
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    # ownership + batas role/department
    permissions.ensure_can_create_user(actor, payload.role, payload.department_id)

    if await UserRepository.get_by_username_or_email(db, payload.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    if await UserRepository.get_by_username_or_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    user = await UserRepository.create_user(db, payload)
    return success_response(
        data=to_json(UserRead.model_validate(user)),
        to_camel=False,
        status_code=status.HTTP_201_CREATED,
        message="User created",
    )


@routerUsers.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    dept_filter = None if actor.role == "superadmin" else actor.department_id
    rows = await UserRepository.list_users(db, department_id=dept_filter)
    data = [to_json(UserRead.model_validate(u)) for u in rows]
    return success_response(data=data, to_camel=False, message="Users retrieved")


@routerUsers.get("/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    permissions.ensure_can_manage_user(actor, user)  # admin hanya drafter di dept-nya
    return success_response(data=to_json(UserRead.model_validate(user)), to_camel=False, message="User retrieved")


@routerUsers.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    permissions.ensure_can_manage_user(actor, user)

    data = payload.model_dump(exclude_unset=True)
    if "role" in data or "department_id" in data:
        permissions.ensure_can_change_role_or_department(actor)

    was_active = user.is_active
    updated = await UserRepository.update_user(db, user, payload)

    # Baru dinonaktifkan -> cabut semua sesi
    if was_active and updated.is_active is False:
        await AuthRepository.revoke_all_for_user(db, updated.id)

    return success_response(data=to_json(UserRead.model_validate(updated)), to_camel=False, message="User updated")


@routerUsers.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    permissions.ensure_can_manage_user(actor, user)
    await UserRepository.set_password(db, user, payload.new_password)
    await AuthRepository.revoke_all_for_user(db, user.id)
    return success_response(data={"reset": True}, message="Password reset")
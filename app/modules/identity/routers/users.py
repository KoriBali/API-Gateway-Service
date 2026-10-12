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
from app.utils.response import success_response
from app.database.models.identity import UserRole
from app.modules.identity import permissions
from app.modules.identity.repository import UserRepository, AuthRepository, DepartmentRepository
from app.modules.identity.schemas import (
    UserCreate,
    UserUpdate,
    PasswordChangeRequest,
    PasswordResetRequest,
    UserRead,
)

routerUsers = APIRouter(prefix="/api/users", tags=["Users"])


def _ensure_reviewer_without_department(role, department_id: str | None) -> None:
    """yoshimoto_reviewer tidak terikat department (V6)."""
    if role == UserRole.yoshimoto_reviewer and department_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="yoshimoto_reviewer must not belong to a department (send departmentId: null)",
        )


# ===== Self User Endpoint =====
@routerUsers.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    user = await UserRepository.get_by_id(db, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return success_response(data=UserRead.model_validate(user), message="Current user")


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
    actor: CurrentUser = Depends(require_roles("superadmin", "admin_department")),
):
    # ownership + batas role/department
    permissions.ensure_can_create_user(actor, payload.role, payload.department_id)
    _ensure_reviewer_without_department(payload.role, payload.department_id)

    # Gunakan find_identity_conflicts yang ada di Repository untuk detect conflict
    conflicts = await UserRepository.find_identity_conflicts(
        db, username=payload.username, email=payload.email
    )
    if "username" in conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already in use as a username or email of another account",
        )
    if "email" in conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already in use as a username or email of another account",
        )
        
    if payload.department_id is not None and not await DepartmentRepository.exists(db, payload.department_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="departmentId does not reference an existing department",
        )


    user = await UserRepository.create_user(db, payload)
    return success_response(
        data=UserRead.model_validate(user),
        status_code=status.HTTP_201_CREATED,
        message="User created",
    )


@routerUsers.get("")
async def list_users(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin_department")),
):
    dept_filter = None if actor.role == "superadmin" else actor.department_id
    rows = await UserRepository.list_users(db, department_id=dept_filter)
    data = [UserRead.model_validate(u) for u in rows]
    return success_response(data=data, message="Users retrieved")


@routerUsers.get("/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin_department")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    permissions.ensure_can_manage_user(actor, user)  # admin hanya drafter di dept-nya
    return success_response(data=UserRead.model_validate(user), message="User retrieved")


@routerUsers.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin_department")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    permissions.ensure_can_manage_user(actor, user)

    data = payload.model_dump(exclude_unset=True)
    
    role_changed = "role" in data and data["role"] != user.role
    department_changed = "department_id" in data and data["department_id"] != user.department_id
    
    if role_changed or department_changed:
        permissions.ensure_can_change_role_or_department(
            actor, data.get("role") if role_changed else None, department_changed
        )
    # Diperiksa pada keadaan SESUDAH perubahan.
    _ensure_reviewer_without_department(
        data.get("role", user.role),
        data["department_id"] if "department_id" in data else user.department_id,
    )


    if "department_id" in data and data["department_id"] is not None \
            and not await DepartmentRepository.exists(db, data["department_id"]):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="departmentId does not reference an existing department",
        )

    was_active = user.is_active
    updated = await UserRepository.update_user(db, user, payload)

    # Baru dinonaktifkan -> cabut semua sesi
    if was_active and updated.is_active is False:
        await AuthRepository.revoke_all_for_user(db, updated.id)

    return success_response(data=UserRead.model_validate(updated), message="User updated")


@routerUsers.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin_department")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    permissions.ensure_can_manage_user(actor, user)
    await UserRepository.set_password(db, user, payload.new_password)
    await AuthRepository.revoke_all_for_user(db, user.id)
    return success_response(data={"reset": True}, message="Password reset")
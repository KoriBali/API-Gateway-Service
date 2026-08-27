from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    CurrentUser,
    get_current_user,
    require_roles,
    create_access_token,
    generate_refresh_token,
    verify_password,
)
from app.utils.response import success_response
from app.modules.identity import permissions
from app.modules.identity.repository import UserRepository, AuthRepository
from app.modules.identity.schemas import (
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    UserCreate,
    UserUpdate,
    PasswordChangeRequest,
    PasswordResetRequest,
    UserRead,
    TokenPair,
)

routerIdentity = APIRouter(prefix="/api/identity", tags=["Identity"])


def _json(model) -> dict | list:
    return jsonable_encoder(model, by_alias=True)


async def _issue_tokens(db: AsyncSession, user) -> TokenPair:
    access = create_access_token(user)
    raw_refresh = generate_refresh_token()
    await AuthRepository.issue_refresh_token(db, user.id, raw_refresh)
    return TokenPair(access_token=access, refresh_token=raw_refresh)



# ===== Auth Endpoint =====
@routerIdentity.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await AuthRepository.authenticate(db, payload.username_or_email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    await UserRepository.update_last_login(db, user)
    tokens = await _issue_tokens(db, user)
    return success_response(data=_json(tokens), to_camel=False, message="Login success")


@routerIdentity.post("/refresh")
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    rt = await AuthRepository.find_by_raw(db, payload.refresh_token)
    if rt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # token yang sudah revoked dipakai lagi
    if rt.revoked:
        await AuthRepository.revoke_all_for_user(db, rt.user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected")

    # Normalisasi 
    expires_at = rt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = await UserRepository.get_by_id(db, rt.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")

    new_raw = generate_refresh_token()
    await AuthRepository.rotate_refresh_token(db, rt, user.id, new_raw)
    tokens = TokenPair(access_token=create_access_token(user), refresh_token=new_raw)
    return success_response(data=_json(tokens), to_camel=False, message="Token refreshed")


@routerIdentity.post("/logout")
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    rt = await AuthRepository.find_by_raw(db, payload.refresh_token)
    if rt is not None and rt.user_id == current.id and not rt.revoked:
        await AuthRepository.revoke(db, rt)
    # token tak dikenal/orang lain tetap 200 (tak membocorkan info)
    return success_response(data={"revoked": True}, message="Logged out")



# ===== Self User Endpoint =====
@routerIdentity.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    user = await UserRepository.get_by_id(db, current.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return success_response(data=_json(UserRead.model_validate(user)), to_camel=False, message="Current user")


@routerIdentity.post("/me/password")
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
@routerIdentity.post("/users")
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
        data=_json(UserRead.model_validate(user)),
        to_camel=False,
        status_code=status.HTTP_201_CREATED,
        message="User created",
    )


@routerIdentity.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    dept_filter = None if actor.role == "superadmin" else actor.department_id
    rows = await UserRepository.list_users(db, department_id=dept_filter)
    data = [_json(UserRead.model_validate(u)) for u in rows]
    return success_response(data=data, to_camel=False, message="Users retrieved")


@routerIdentity.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    actor: CurrentUser = Depends(require_roles("superadmin", "admin")),
):
    user = await UserRepository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    permissions.ensure_can_manage_user(actor, user)  # admin hanya drafter di dept-nya
    return success_response(data=_json(UserRead.model_validate(user)), to_camel=False, message="User retrieved")


@routerIdentity.patch("/users/{user_id}")
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

    return success_response(data=_json(UserRead.model_validate(updated)), to_camel=False, message="User updated")


@routerIdentity.post("/users/{user_id}/reset-password")
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
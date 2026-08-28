from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    CurrentUser,
    get_current_user,
    create_access_token,
    generate_refresh_token,
)
from app.utils.response import success_response, to_json
from app.modules.identity.repository import UserRepository, AuthRepository
from app.modules.identity.schemas import (
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    TokenPair,
)

routerAuth = APIRouter(prefix="/api/auth", tags=["Auth"])



async def _issue_tokens(db: AsyncSession, user) -> TokenPair:
    access = create_access_token(user)
    raw_refresh = generate_refresh_token()
    await AuthRepository.issue_refresh_token(db, user.id, raw_refresh)
    return TokenPair(access_token=access, refresh_token=raw_refresh)



# ===== Auth Endpoint =====
@routerAuth.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await AuthRepository.authenticate(db, payload.username_or_email, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    await UserRepository.update_last_login(db, user)
    tokens = await _issue_tokens(db, user)
    return success_response(data=to_json(tokens), to_camel=False, message="Login success")


@routerAuth.post("/refresh")
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
    return success_response(data=to_json(tokens), to_camel=False, message="Token refreshed")


@routerAuth.post("/logout")
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
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    hash_token,
)
from app.database.models.identity import User, RefreshToken
from app.modules.identity.schemas import UserCreate, UserUpdate



# ===== User =====
class UserRepository:

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username_or_email(db: AsyncSession, identifier: str) -> User | None:
        stmt = select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_users(db: AsyncSession, department_id: str | None = None) -> list[User]:
        # List semua jika tanpa Department_id
        stmt = select(User)
        if department_id is not None:
            stmt = stmt.where(User.department_id == department_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_user(db: AsyncSession, payload: UserCreate) -> User:
        user = User(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=payload.role,
            department_id=payload.department_id,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user: User, payload: UserUpdate) -> User:
        data = payload.model_dump(exclude_unset=True)
        for field in ("full_name", "is_active", "role", "department_id"):
            if field in data:
                setattr(user, field, data[field])
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_active(db: AsyncSession, user: User, is_active: bool) -> User:
        user.is_active = is_active
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def set_password(db: AsyncSession, user: User, new_password: str) -> User:
        user.password_hash = hash_password(new_password)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_last_login(db: AsyncSession, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()



# ===== Auth ======
class AuthRepository:

    @staticmethod
    async def authenticate(db: AsyncSession, identifier: str, password: str) -> User | None:
        # Return User apabila credential & is_active = true
        user = await UserRepository.get_by_username_or_email(db, identifier)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def issue_refresh_token(db: AsyncSession, user_id: str, raw_token: str) -> RefreshToken:
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        rt = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            revoked=False,
        )
        db.add(rt)
        await db.commit()
        await db.refresh(rt)
        return rt

    @staticmethod
    async def find_by_raw(db: AsyncSession, raw_token: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke(db: AsyncSession, rt: RefreshToken) -> None:
        rt.revoked = True
        await db.commit()

    @staticmethod
    async def revoke_all_for_user(db: AsyncSession, user_id: str) -> int:
        stmt = (
            sa_update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
            .values(revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession, old_rt: RefreshToken, user_id: str, new_raw_token: str
    ) -> RefreshToken:
        """Atomik: revoke token lama + terbitkan token baru (satu commit)."""
        old_rt.revoked = True
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        new_rt = RefreshToken(
            user_id=user_id,
            token_hash=hash_token(new_raw_token),
            expires_at=expires_at,
            revoked=False,
        )
        db.add(new_rt)
        await db.commit()
        await db.refresh(new_rt)
        return new_rt
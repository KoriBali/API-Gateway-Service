from datetime import datetime, timezone, timedelta, date
from typing import TYPE_CHECKING

from sqlalchemy import select, or_, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    hash_token,
)
from app.database.models.identity import User, RefreshToken, Department, Request
from app.modules.identity.schemas import (
    UserCreate, UserUpdate,
    DepartmentCreate, DepartmentUpdate,
    RequestCreate, RequestUpdate,
)

from app.database.models.master import PoleCategory
from app.database.models.calculation import CalculationCase
from app.database.models.drawing import DrawingCase



if TYPE_CHECKING:
    from app.database.models.identity import (
        RequestType, RequestCategory, DesignType
    )



# ===== Request =====
class RequestRepository:

    @staticmethod
    async def get_by_id(db: AsyncSession, request_id: str) -> Request | None:
        result = await db.execute(select(Request).where(Request.id == request_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def pole_category_exists(db: AsyncSession, pole_category_id: str) -> bool:
        found = await db.scalar(
            select(PoleCategory.id).where(PoleCategory.id == pole_category_id)
        )
        return found is not None

    @staticmethod
    async def list_scoped(
        db: AsyncSession,
        *,
        role: str,
        actor_id: str,
        actor_department_id: str | None,
        request_type: "RequestType | None" = None,
        request_category: "RequestCategory | None" = None,
        design_type: "DesignType | None" = None,
        pole_category_id: str | None = None,
        due_from: date | None = None,
        due_to: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Request], int]:
        stmt = select(Request)

        # Scope per Role
        if role == "superadmin":
            pass 
        elif role == "admin":
            stmt = stmt.where(Request.responsible_department_id == actor_department_id)
        else: 
            stmt = stmt.where(Request.created_by_user_id == actor_id)

        # Filter opsional
        if request_type is not None:
            stmt = stmt.where(Request.request_type == request_type)
        if request_category is not None:
            stmt = stmt.where(Request.request_category == request_category)
        if design_type is not None:
            stmt = stmt.where(Request.design_type == design_type)
        if pole_category_id is not None:
            stmt = stmt.where(Request.pole_category_id == pole_category_id)
        if due_from is not None:
            stmt = stmt.where(Request.due_date >= due_from)
        if due_to is not None:
            stmt = stmt.where(Request.due_date <= due_to)

        # Total 
        total = await db.scalar(
            select(func.count()).select_from(stmt.subquery())
        )

        # Halaman data
        stmt = stmt.order_by(Request.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        return rows, int(total or 0)

    @staticmethod
    async def create(
        db: AsyncSession,
        payload: RequestCreate,
        *,
        created_by_user_id: str,
        responsible_department_id: str,
    ) -> Request:
        req = Request(
            responsible_department_id=responsible_department_id,
            created_by_user_id=created_by_user_id,
            pole_category_id=payload.pole_category_id,
            request_no=payload.request_no,
            receipt_no=payload.receipt_no,
            pj_no=payload.pj_no,
            request_type=payload.request_type,
            design_type=payload.design_type,
            request_category=payload.request_category,
            pole_kind=payload.pole_kind,
            company_name=payload.company_name,
            project_name=payload.project_name,
            due_date=payload.due_date,
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def update(db: AsyncSession, req: Request, payload: RequestUpdate) -> Request:
        data = payload.model_dump(exclude_unset=True)
        editable = (
            "pole_category_id", "request_no", "receipt_no", "pj_no",
            "request_type", "design_type", "request_category",
            "pole_kind", "company_name", "project_name", "due_date",
        )
        for field in editable:
            if field in data:
                setattr(req, field, data[field])
        await db.commit()
        await db.refresh(req)
        return req

    @staticmethod
    async def count_children(db: AsyncSession, request_id: str) -> tuple[int, int]:
        calc_count = await db.scalar(
            select(func.count()).select_from(CalculationCase).where(
                CalculationCase.request_id == request_id
            )
        )
        draw_count = await db.scalar(
            select(func.count()).select_from(DrawingCase).where(
                DrawingCase.request_id == request_id
            )
        )
        return int(calc_count or 0), int(draw_count or 0)

    @staticmethod
    async def delete(db: AsyncSession, req: Request) -> None:
        await db.delete(req)
        await db.commit()



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



# ===== Department =====
class DepartmentRepository:

    @staticmethod
    async def get_by_id(db: AsyncSession, department_id: str) -> Department | None:
        result = await db.execute(select(Department).where(Department.id == department_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: str) -> Department | None:
        result = await db.execute(select(Department).where(Department.code == code))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, name: str) -> Department | None:
        result = await db.execute(select(Department).where(Department.name == name))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all(db: AsyncSession) -> list[Department]:
        result = await db.execute(select(Department).order_by(Department.code))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, payload: DepartmentCreate) -> Department:
        dept = Department(code=payload.code, name=payload.name)
        db.add(dept)
        await db.commit()
        await db.refresh(dept)
        return dept

    @staticmethod
    async def update(db: AsyncSession, dept: Department, payload: DepartmentUpdate) -> Department:
        data = payload.model_dump(exclude_unset=True)
        for field in ("code", "name"):
            if field in data:
                setattr(dept, field, data[field])
        await db.commit()
        await db.refresh(dept)
        return dept

    @staticmethod
    async def count_usage(db: AsyncSession, department_id: str) -> tuple[int, int]:
        user_count = await db.scalar(
            select(func.count()).select_from(User).where(User.department_id == department_id)
        )
        request_count = await db.scalar(
            select(func.count()).select_from(Request).where(
                Request.responsible_department_id == department_id
            )
        )
        return int(user_count or 0), int(request_count or 0)

    @staticmethod
    async def delete(db: AsyncSession, dept: Department) -> None:
        await db.delete(dept)
        await db.commit()
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.identity import User, UserRole
from app.database.models.intake import Request
from app.database.models.workflow import (
    AssignmentStatus,
    RequestAssignment,
    RevisionRound,
    WorkHour,
    WorkType,
)


class DuplicateActiveAssignment(Exception):
    """Orang ini sudah punya assignment aktif untuk work type itu di request yang sama."""



# ===== Request Assignment =====
class AssignmentRepository:

    @staticmethod
    def assigned_clause(user_id: str):
        """Kondisi SQL 'user ini pernah punya assignment di request ini', aktif maupun released.
        Berkorelasi ke Request.id, dipakai di WHERE query daftar request."""
        return exists().where(
            RequestAssignment.request_id == Request.id,
            RequestAssignment.assignee_user_id == user_id,
        )

    @staticmethod
    def active_worker_clause():
        """Kondisi SQL 'request ini punya minimal satu assignment aktif'"""
        return exists().where(
            RequestAssignment.request_id == Request.id,
            RequestAssignment.assignment_status == AssignmentStatus.active,
        )

    @staticmethod
    async def has_any(db: AsyncSession, request_id: str, user_id: str) -> bool:
        stmt = select(exists().where(
            RequestAssignment.request_id == request_id,
            RequestAssignment.assignee_user_id == user_id,
        ))
        return bool(await db.scalar(stmt))

    @staticmethod
    async def has_active(
        db: AsyncSession, request_id: str, user_id: str, work_type: WorkType | None = None,
    ) -> bool:
        """Assignment aktif user ini di request ini; dipersempit ke satu work type bila diisi."""
        conditions = [
            RequestAssignment.request_id == request_id,
            RequestAssignment.assignee_user_id == user_id,
            RequestAssignment.assignment_status == AssignmentStatus.active,
        ]
        if work_type is not None:
            conditions.append(RequestAssignment.work_type == work_type)
        return bool(await db.scalar(select(exists().where(*conditions))))

    @staticmethod
    async def get_user(db: AsyncSession, user_id: str) -> User | None:
        return await db.scalar(select(User).where(User.id == user_id))
    
    @staticmethod
    async def list_assignable_users(
        db: AsyncSession, department_id: str, roles: frozenset[UserRole]
    ) -> list[User]:
        """Active User in one Department yang boleh di assign: drafter, drafter_checker, admin_department"""
        result = await db.execute(
            select(User)
            .where(
                User.department_id == department_id,
                User.is_active.is_(True),
                User.role.in_(roles)
            )
            .order_by(User.full_name, User.username)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_in_request(
        db: AsyncSession, request_id: str, assignment_id: str, *, for_update: bool = False,
    ) -> RequestAssignment | None:
        stmt = (
            select(RequestAssignment)
            .where(
                RequestAssignment.id == assignment_id,
                RequestAssignment.request_id == request_id,
            )
            .options(selectinload(RequestAssignment.assignee))
        )
        if for_update:
            # Kunci hanya baris assignment, bukan tabel users yang ikut dimuat.
            stmt = stmt.with_for_update(of=RequestAssignment)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def list_with_hours(
        db: AsyncSession, request_id: str,
    ) -> list[tuple[RequestAssignment, Decimal]]:
        """Semua assignment satu request (aktif dan released) beserta jumlah jamnya."""
        total = (
            select(func.coalesce(func.sum(WorkHour.hours), 0))
            .where(WorkHour.request_assignment_id == RequestAssignment.id)
            .scalar_subquery()
        )
        stmt = (
            select(RequestAssignment, total)
            .where(RequestAssignment.request_id == request_id)
            .options(selectinload(RequestAssignment.assignee))
            .order_by(RequestAssignment.assigned_at, RequestAssignment.id)
        )
        return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        request_id: str,
        assignee_user_id: str,
        work_type: WorkType,
        assigned_by_user_id: str,
    ) -> RequestAssignment:
        row = RequestAssignment(
            request_id=request_id,
            assignee_user_id=assignee_user_id,
            work_type=work_type,
            assigned_by_user_id=assigned_by_user_id,
            assignment_status=AssignmentStatus.active,
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError as exc:
            # Dua penambahan bersamaan untuk orang dan work type yang sama:
            # index uq_request_assignments_active_per_worker menolak yang kedua.
            await db.rollback()
            if "uq_request_assignments_active_per_worker" in str(exc.orig):
                raise DuplicateActiveAssignment() from exc
            raise
        return await AssignmentRepository.get_in_request(db, request_id, row.id)

    @staticmethod
    async def release(db: AsyncSession, row: RequestAssignment, *, released_by_user_id: str) -> RequestAssignment:
        """Pemanggil wajib sudah mengunci baris (get_in_request for_update=True)."""
        row.assignment_status = AssignmentStatus.released
        row.released_at = datetime.now(timezone.utc)
        row.released_by_user_id = released_by_user_id
        await db.commit()
        return row



# ===== Work Hour =====
class WorkHourRepository:

    @staticmethod
    async def list_for_assignment(db: AsyncSession, assignment_id: str) -> list[WorkHour]:
        stmt = (
            select(WorkHour)
            .where(WorkHour.request_assignment_id == assignment_id)
            .order_by(WorkHour.work_date, WorkHour.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_in_assignment(db: AsyncSession, assignment_id: str, work_hour_id: str) -> WorkHour | None:
        stmt = select(WorkHour).where(
            WorkHour.id == work_hour_id,
            WorkHour.request_assignment_id == assignment_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def round_in_request(db: AsyncSession, request_id: str, revision_round_id: str) -> bool:
        stmt = select(exists().where(
            RevisionRound.id == revision_round_id,
            RevisionRound.request_id == request_id,
        ))
        return bool(await db.scalar(stmt))

    @staticmethod
    async def create(db: AsyncSession, assignment_id: str, data: dict) -> WorkHour:
        row = WorkHour(request_assignment_id=assignment_id, **data)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def update(db: AsyncSession, row: WorkHour, data: dict) -> WorkHour:
        for field, value in data.items():
            setattr(row, field, value)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def delete(db: AsyncSession, row: WorkHour) -> None:
        await db.delete(row)
        await db.commit()

    @staticmethod
    async def summary_by_work_type(db: AsyncSession, request_id: str) -> list[tuple[WorkType, Decimal]]:
        stmt = (
            select(RequestAssignment.work_type, func.sum(WorkHour.hours))
            .join(WorkHour, WorkHour.request_assignment_id == RequestAssignment.id)
            .where(RequestAssignment.request_id == request_id)
            .group_by(RequestAssignment.work_type)
            .order_by(RequestAssignment.work_type)
        )
        return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]

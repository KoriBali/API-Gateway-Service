from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.intake import Request
from app.modules.workflow.gate import apply_prevention_status


from app.database.models.calculation import CalculationCase
from app.database.models.drawing import DrawingCase

# Field header yang boleh ditulis dari payload (whitelist).
_CASE_HEADER_FIELDS = (
    "title",
    "case_label",
    "pole_kind",
    "drawing_type",
    "drawing_number",
    "part_number",
    "calculation_case_id",
)


class DrawingCaseRepository:
    """Satu request boleh punya banyak drawing case"""

    @staticmethod
    async def list_by_request(db: AsyncSession, request_id: str) -> list[DrawingCase]:
        stmt = (
            select(DrawingCase)
            .where(DrawingCase.request_id == request_id)
            .order_by(DrawingCase.created_at, DrawingCase.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_in_request(db: AsyncSession, request_id: str, case_id: str) -> DrawingCase | None:
        stmt = select(DrawingCase).where(
            DrawingCase.id == case_id,
            DrawingCase.request_id == request_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def calculation_case_in_request(db: AsyncSession, request_id: str, calculation_case_id: str) -> bool:
        """Acuan perhitungan harus calculation case di request yang sama (juga dijaga FK komposit)."""
        stmt = select(exists().where(
            CalculationCase.id == calculation_case_id,
            CalculationCase.request_id == request_id,
        ))
        return bool(await db.scalar(stmt))

    @staticmethod
    async def create(
        db: AsyncSession, req: Request, *, owner_user_id: str, data: dict,
    ) -> DrawingCase:
        """Pembuat case = owner pertamanya. data sudah memuat title (G5) dan drawing_type (G8)."""
        case = DrawingCase(
            request_id=req.id,
            created_by_user_id=owner_user_id,
            owner_user_id=owner_user_id,
        )
        for field in _CASE_HEADER_FIELDS:
            if field in data:
                setattr(case, field, data[field])
        db.add(case)
        await db.flush()
        # Case baru belum diperiksa: status bisa turun dari prevention_check.
        await apply_prevention_status(db, req)
        await db.commit()

        await db.refresh(case)
        return case

    @staticmethod
    async def update(db: AsyncSession, case: DrawingCase, data: dict) -> DrawingCase:
        for field in _CASE_HEADER_FIELDS:
            if field in data:
                setattr(case, field, data[field])
        await db.commit()
        await db.refresh(case)
        return case

    @staticmethod
    async def delete(db: AsyncSession, req: Request, case: DrawingCase) -> None:
        """Anak case ikut terhapus (ON DELETE CASCADE). Peristiwa case tetap tersimpan"""
        await db.delete(case)
        await db.flush()
        # Case yang belum diperiksa hilang: syarat prevention_check bisa berubah.
        await apply_prevention_status(db, req)
        await db.commit()


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.intake import Request
from app.modules.workflow.gate import apply_prevention_status

from app.database.models.calculation import CalculationCase

# Field skalar yang boleh ditulis dari payload (whitelist).
_CASE_SCALAR_FIELDS = (
    "title",
    "pole_standard_id",
    "pole_standard_height_id",
    "pole_combination_id",
    "pole_family",
    "ground_position",
    "lowest_height",
    "embedment_length",
    "overdesign_factor",
    "pole_kind",
    "case_label",
)


class CalculationCaseRepository:
    """Satu request boleh punya banyak calculation case"""

    @staticmethod
    async def list_by_request(db: AsyncSession, request_id: str) -> list[CalculationCase]:
        stmt = (
            select(CalculationCase)
            .where(CalculationCase.request_id == request_id)
            .order_by(CalculationCase.created_at, CalculationCase.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_in_request(db: AsyncSession, request_id: str, case_id: str) -> CalculationCase | None:
        stmt = select(CalculationCase).where(
            CalculationCase.id == case_id,
            CalculationCase.request_id == request_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession, req: Request, *, owner_user_id: str, data: dict,
    ) -> CalculationCase:
        """Pembuat case = owner pertamanya. created_by_user_id tidak pernah berganti
        data sudah memuat title hasil isian awal G5."""
        case = CalculationCase(
            request_id=req.id,
            created_by_user_id=owner_user_id,
            owner_user_id=owner_user_id,
        )
        for field in _CASE_SCALAR_FIELDS:
            if field in data:
                setattr(case, field, data[field])
        # TODO(calc-contract): tulis komponen (openings/baseplates/foundations) di transaksi
        #   yang sama, setelah field domain difinalkan. Terapkan aturan "lengkap-atau-lewati"
        #   karena kolomnya banyak yang NOT NULL.
        db.add(case)
        await db.flush()
        # Case baru belum diperiksa: status bisa turun dari prevention_check
        await apply_prevention_status(db, req)
        await db.commit()

        await db.refresh(case)
        return case

    @staticmethod
    async def update(db: AsyncSession, case: CalculationCase, data: dict) -> CalculationCase:
        for field in _CASE_SCALAR_FIELDS:
            if field in data:
                setattr(case, field, data[field])
        # TODO(calc-contract): tulis-ulang komponen dengan pola delete-then-insert.
        await db.commit()
        await db.refresh(case)
        return case

    @staticmethod
    async def delete(db: AsyncSession, req: Request, case: CalculationCase) -> None:
        """Anak case ikut terhapus (ON DELETE CASCADE). Drawing case yang mengacu case ini
        kehilangan acuannya (SET NULL). Peristiwa case tetap tersimpan"""
        await db.delete(case)
        await db.flush()
        # Case yang belum diperiksa hilang: syarat prevention_check bisa berubah.
        await apply_prevention_status(db, req)
        await db.commit()

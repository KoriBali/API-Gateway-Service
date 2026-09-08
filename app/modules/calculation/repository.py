from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.calculation import CalculationCase, Condition
from app.modules.calculation.schemas import CalculationCaseUpsert

# Field skalar yang boleh di-update dari payload (whitelist).
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
)


class CalculationCaseRepository:

    @staticmethod
    async def get_by_request(db: AsyncSession, request_id: str) -> CalculationCase | None:
        """Ambil satu-satunya calc case milik request (jaminan 1:1)."""
        res = await db.execute(
            select(CalculationCase).where(CalculationCase.request_id == request_id)
        )
        return res.scalars().first()

    @staticmethod
    async def get_with_children(db: AsyncSession, request_id: str) -> CalculationCase | None:
        """Untuk resume: case + condition (anak lain menyusul saat dipetakan)."""
        res = await db.execute(
            select(CalculationCase)
            .where(CalculationCase.request_id == request_id)
            .options(selectinload(CalculationCase.conditions))
        )
        return res.scalars().first()

    @staticmethod
    async def upsert(
        db: AsyncSession,
        *,
        request_id: str,
        owner_user_id: str,
        payload: CalculationCaseUpsert,
    ) -> CalculationCase:
        """Buat/-update satu calc case + tulis-ulang anaknya dalam SATU transaksi."""
        case = await CalculationCaseRepository.get_by_request(db, request_id)
        data = payload.model_dump(exclude_unset=True)

        if case is None:
            # CREATE: title NOT NULL -> default bila FE belum mengirim.
            case = CalculationCase(
                request_id=request_id,
                owner_user_id=owner_user_id,
                title=data.get("title") or "Untitled draft",
            )
            db.add(case)
            await db.flush()  

        # UPDATE field skalar 
        for field in _CASE_SCALAR_FIELDS:
            if field in data:
                setattr(case, field, data[field])

        await db.execute(
            delete(Condition).where(Condition.calculation_case_id == case.id)
        )
        cond = payload.condition
        if cond is not None and None not in (
            cond.design_standard_id, cond.wind_speed, cond.air_density
        ):
            db.add(Condition(
                calculation_case_id=case.id,
                design_standard_id=cond.design_standard_id,
                wind_speed=cond.wind_speed,
                air_density=cond.air_density,
            ))

        # TODO(calc-contract): tulis-ulang komponen (openings/baseplates/foundations)
        #   dengan pola delete-then-insert yang sama, setelah field domain difinalkan.
        #   Terapkan aturan "lengkap-atau-lewati" karena kolomnya banyak yang NOT NULL.

        await db.commit()
        await db.refresh(case)
        return case
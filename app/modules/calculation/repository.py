from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.calculation import CalculationCase
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
    "pole_kind",
    "case_label",
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
    async def upsert(
        db: AsyncSession,
        *,
        request_id: str,
        owner_user_id: str,
        payload: CalculationCaseUpsert,
    ) -> CalculationCase:
        """Buat/-update satu calc case + tulis-ulang anaknya dalam SATU transaksi.
        Conditions milik request (PATCH /api/requests/{id}/conditions), bukan milik case."""
        case = await CalculationCaseRepository.get_by_request(db, request_id)
        data = payload.model_dump(exclude_unset=True)

        if case is None:
            # CREATE: title NOT NULL -> default bila FE belum mengirim.
            case = CalculationCase(
                request_id=request_id,
                # Pembuat case = owner pertamanya. created_by tidak pernah berganti
                created_by_user_id=owner_user_id,
                owner_user_id=owner_user_id,
                title=data.get("title") or "Untitled draft",
                pole_kind=data["pole_kind"],
            )

            db.add(case)
            await db.flush()  

        # UPDATE field skalar 
        for field in _CASE_SCALAR_FIELDS:
            if field in data:
                setattr(case, field, data[field])

        # TODO(calc-contract): tulis-ulang komponen (openings/baseplates/foundations)
        #   dengan pola delete-then-insert yang sama, setelah field domain difinalkan.
        #   Terapkan aturan "lengkap-atau-lewati" karena kolomnya banyak yang NOT NULL.

        await db.commit()
        await db.refresh(case)
        return case
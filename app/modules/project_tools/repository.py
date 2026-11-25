from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.master import PoleStandardHeight, PoleStandardStepPole


def catalog_shape(height, step_poles) -> tuple:
    """Bentuk geometri katalog yang dipakai Hitung: step pole dan posisi cek.
    step_poles boleh objek ORM atau baris hasil select kolom (atribut bernama sama)."""
    return (
        sorted(
            (s.name, s.pole_type, s.material_id, s.top_elevation_m, s.diameter_lower_mm,
             s.diameter_upper_mm, s.thickness_lower_mm, s.thickness_upper_mm)
            for s in step_poles
        ),
        list(height.evaluated_positions_m or []),
    )


def comparable_shape(shape: tuple | None) -> tuple | None:
    """catalog_shape dengan angka sebagai float dan posisi cek terurut, supaya geometri dari
    body (float) bisa dibandingkan dengan katalog (Decimal). Urutan posisi tidak mengubah hasil."""
    if shape is None:
        return None
    step_poles, positions = shape
    to_float = lambda v: float(v) if isinstance(v, (Decimal, int, float)) and not isinstance(v, bool) else v
    return (
        sorted(tuple(to_float(v) for v in row) for row in step_poles),
        sorted(float(p) for p in positions),
    )


class ProjectToolRepository:

    @staticmethod
    async def fresh_catalog_shape(db: AsyncSession, height_id: str) -> tuple | None:
        """catalog_shape langsung dari database. Select kolom, bukan entity: nilainya tidak
        diambil dari identity map sesi, jadi perubahan katalog sesudah Hitung terlihat.
        None bila pilihan tinggi sudah tidak aktif."""
        height = (await db.execute(
            select(PoleStandardHeight.evaluated_positions_m)
            .where(PoleStandardHeight.id == height_id, PoleStandardHeight.is_active.is_(True))
        )).first()
        if height is None:
            return None
        step_poles = (await db.execute(
            select(
                PoleStandardStepPole.name, PoleStandardStepPole.pole_type,
                PoleStandardStepPole.material_id, PoleStandardStepPole.top_elevation_m,
                PoleStandardStepPole.diameter_lower_mm, PoleStandardStepPole.diameter_upper_mm,
                PoleStandardStepPole.thickness_lower_mm, PoleStandardStepPole.thickness_upper_mm,
            ).where(PoleStandardStepPole.pole_standard_height_id == height_id)
        )).all()
        return catalog_shape(height, step_poles)

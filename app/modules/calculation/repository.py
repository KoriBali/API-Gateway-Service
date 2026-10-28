from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.models.intake import Request
from app.modules.workflow.gate import apply_prevention_status

from app.database.models.calculation import (
    CalculationCase,
    CalculationRun,
    CalculationRunType,
    PoleFamily,
    PoleKind,
    StatusCalculationRun,
)
from app.database.models.calculation_object import DirectObject, StepPole
from app.database.models.master import (
    DesignStandard,
    Material,
    PoleStandardHeight,
    PoleStandardSegment,
)

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
    async def get_in_request(
        db: AsyncSession, request_id: str, case_id: str, *, for_update: bool = False,
    ) -> CalculationCase | None:
        stmt = select(CalculationCase).where(
            CalculationCase.id == case_id,
            CalculationCase.request_id == request_id,
        )
        if for_update:
            # Simpan menghapus lalu meng-insert ulang anak case: dua Simpan bersamaan diantrikan.
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_detail(db: AsyncSession, case_id: str) -> CalculationCase:
        """Case beserta segmen dan objek langsung, untuk CalculationCaseDetail."""
        stmt = (
            select(CalculationCase)
            .where(CalculationCase.id == case_id)
            .options(
                selectinload(CalculationCase.step_poles),
                selectinload(CalculationCase.direct_objects),
            )
            .execution_options(populate_existing=True)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def get_height_for_calculation(db: AsyncSession, height_id: str) -> PoleStandardHeight | None:
        """Pilihan tinggi aktif beserta standar, segmen (dengan material), dan objek katalog."""
        stmt = (
            select(PoleStandardHeight)
            .where(PoleStandardHeight.id == height_id, PoleStandardHeight.is_active == True)
            .options(
                selectinload(PoleStandardHeight.pole_standard),
                selectinload(PoleStandardHeight.segments).selectinload(PoleStandardSegment.material),
                selectinload(PoleStandardHeight.direct_objects),
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_design_standard(db: AsyncSession, design_standard_id: str) -> DesignStandard:
        return (await db.execute(
            select(DesignStandard).where(DesignStandard.id == design_standard_id)
        )).scalar_one()

    @staticmethod
    async def material_names(db: AsyncSession, material_ids) -> dict[str, str]:
        rows = (await db.execute(
            select(Material.id, Material.name).where(Material.id.in_(set(material_ids)))
        )).all()
        return {row.id: row.name for row in rows}

    @staticmethod
    async def geometry_differs_from_catalog(db: AsyncSession, case: CalculationCase) -> bool | None:
        """Keterangan DD BAB 13: segmen dan posisi cek case dibanding katalog saat ini.
        case.step_poles wajib sudah di-load (get_detail)."""
        if case.pole_kind != PoleKind.standard or case.pole_standard_height_id is None:
            return None
        height = await CalculationCaseRepository.get_height_for_calculation(db, case.pole_standard_height_id)
        if height is None:
            return None

        def shape(rows):
            return sorted(
                (r.name, r.pole_type.value, r.material_id, r.top_elevation_m, r.diameter_lower_mm,
                 r.diameter_upper_mm, r.thickness_lower_mm, r.thickness_upper_mm)
                for r in rows
            )

        return (
            shape(case.step_poles) != shape(height.segments)
            or list(case.evaluated_positions_m or []) != list(height.evaluated_positions_m or [])
        )

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
        await CalculationCaseRepository._sync_catalog_geometry(db, case, previous_height_id=None)
        # Case baru belum diperiksa: status bisa turun dari prevention_check
        await apply_prevention_status(db, req)
        await db.commit()

        await db.refresh(case)
        return case

    @staticmethod
    async def update(db: AsyncSession, case: CalculationCase, data: dict) -> CalculationCase:
        previous_height_id = case.pole_standard_height_id
        for field in _CASE_SCALAR_FIELDS:
            if field in data:
                setattr(case, field, data[field])
        # TODO(calc-contract): tulis-ulang komponen dengan pola delete-then-insert.
        await CalculationCaseRepository._sync_catalog_geometry(db, case, previous_height_id=previous_height_id)
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


    # ===== G1: salinan katalog =====
    @staticmethod
    async def _sync_catalog_geometry(
        db: AsyncSession, case: CalculationCase, *, previous_height_id: str | None, force: bool = False,
    ) -> None:
        """Salin segmen dan posisi cek dari pilihan tinggi ke case tiang standard (G1).

        Hanya saat tinggi diisi atau diganti, saat case belum punya segmen, atau bila
        diminta (force). Simpan dengan tinggi yang sama tidak menyalin ulang, sehingga
        perubahan katalog tidak merambat diam-diam. Tidak commit: ikut transaksi pemanggil.
        """
        if case.pole_kind != PoleKind.standard:
            return
        height_id = case.pole_standard_height_id
        if not force and height_id == previous_height_id:
            has_segments = await db.scalar(
                select(StepPole.id).where(StepPole.calculation_case_id == case.id).limit(1)
            )
            if has_segments is not None or height_id is None:
                return

        await db.execute(delete(StepPole).where(StepPole.calculation_case_id == case.id))
        case.evaluated_positions_m = None
        if height_id is None:
            return
        height = await CalculationCaseRepository.get_height_for_calculation(db, height_id)
        if height is None:
            return
        for segment in height.segments:
            db.add(StepPole(
                calculation_case_id=case.id,
                material_id=segment.material_id,
                name=segment.name,
                pole_type=segment.pole_type,
                top_elevation_m=segment.top_elevation_m,
                diameter_lower_mm=segment.diameter_lower_mm,
                diameter_upper_mm=segment.diameter_upper_mm,
                thickness_lower_mm=segment.thickness_lower_mm,
                thickness_upper_mm=segment.thickness_upper_mm,
                quantity=1,
            ))
        if height.evaluated_positions_m is not None:
            case.evaluated_positions_m = list(height.evaluated_positions_m)

    # ===== Simpan (G15), bagian input =====
    @staticmethod
    async def save_input(db: AsyncSession, case: CalculationCase, height: PoleStandardHeight, data) -> None:
        """Simpan isian perhitungan tiang standard. Pemanggil sudah mengunci case.
        data: CalculationInput. Objek langsung ditulis ulang (hapus lalu insert)."""
        previous_height_id = case.pole_standard_height_id
        case.pole_standard_id = height.pole_standard_id
        case.pole_standard_height_id = height.id
        case.pole_family = PoleFamily.taper
        case.ground_position = data.ground_position
        case.overdesign_factor = data.overdesign_factor
        await CalculationCaseRepository._sync_catalog_geometry(
            db, case, previous_height_id=previous_height_id, force=data.recopy_catalog,
        )

        await db.execute(delete(DirectObject).where(DirectObject.calculation_case_id == case.id))
        for obj in data.direct_objects:
            db.add(DirectObject(calculation_case_id=case.id, **obj.model_dump()))
        await db.commit()

    # ===== Run =====
    @staticmethod
    async def create_run(
        db: AsyncSession, *, case_id: str, run_by_user_id: str, status: StatusCalculationRun,
        input_snapshot: dict, result_snapshot: dict | None, error_snapshot: dict | None,
    ) -> CalculationRun:
        run = CalculationRun(
            calculation_case_id=case_id,
            run_type=CalculationRunType.pole,
            status=status,
            input_snapshot=input_snapshot,
            result_snapshot=result_snapshot,
            error_snapshot=error_snapshot,
            run_by_user_id=run_by_user_id,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    @staticmethod
    async def list_runs(db: AsyncSession, case_id: str) -> list[CalculationRun]:
        stmt = (
            select(CalculationRun)
            .where(CalculationRun.calculation_case_id == case_id)
            .order_by(CalculationRun.run_at.desc(), CalculationRun.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_run(db: AsyncSession, case_id: str, run_id: str) -> CalculationRun | None:
        stmt = select(CalculationRun).where(
            CalculationRun.id == run_id,
            CalculationRun.calculation_case_id == case_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()
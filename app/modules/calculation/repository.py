from datetime import datetime, timezone

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.models.intake import Request
from app.modules.workflow.gate import apply_prevention_status

from app.database.models.calculation import (
    CalculationCase,
    CalculationRun,
    CalculationRunType,
    GroundPosition,
    PoleFamily,
    PoleKind,
    Report,
    StatusCalculationRun,
)
from app.database.models.calculation_object import Arm, ArmObject, DirectObject, OverheadWire, StepPole
from app.database.models.master import (
    AuthorCode,
    DepartmentCode,
    DesignStandard,
    Material,
    PoleStandardHeight,
    PoleStandardStepPole,
    RegionCode,
)

# Field header yang boleh ditulis create dan PATCH (whitelist). Isian perhitungan
# hanya ditulis save_input (Simpan).
_CASE_SCALAR_FIELDS = (
    "title",
    "case_label",
    "pole_kind",
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
        """Case beserta step pole, objek langsung, kawat, dan lengan, untuk CalculationCaseDetail."""
        stmt = (
            select(CalculationCase)
            .where(CalculationCase.id == case_id)
            .options(
                selectinload(CalculationCase.step_poles),
                selectinload(CalculationCase.direct_objects),
                selectinload(CalculationCase.overhead_wires),
                selectinload(CalculationCase.arms).selectinload(Arm.arm_objects),
            )
            .execution_options(populate_existing=True)
        )
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def get_height_for_calculation(db: AsyncSession, height_id: str) -> PoleStandardHeight | None:
        """Pilihan tinggi aktif beserta standar, step pole (dengan material), dan objek katalog."""
        stmt = (
            select(PoleStandardHeight)
            .where(PoleStandardHeight.id == height_id, PoleStandardHeight.is_active == True)
            .options(
                selectinload(PoleStandardHeight.pole_standard),
                selectinload(PoleStandardHeight.step_poles).selectinload(PoleStandardStepPole.material),
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
        """step pole dan posisi cek case dibanding katalog saat ini.
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
            shape(case.step_poles) != shape(height.step_poles)
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
        """Salin step pole dan posisi cek dari pilihan tinggi ke case tiang standard (G1).

        Hanya saat tinggi diisi atau diganti, saat case belum punya step pole, atau bila
        diminta (force). Simpan dengan tinggi yang sama tidak menyalin ulang, sehingga
        perubahan katalog tidak merambat diam-diam. Tidak commit: ikut transaksi pemanggil.
        """
        if case.pole_kind != PoleKind.standard:
            return
        height_id = case.pole_standard_height_id
        if not force and height_id == previous_height_id:
            has_step_poles = await db.scalar(
                select(StepPole.id).where(StepPole.calculation_case_id == case.id).limit(1)
            )
            if has_step_poles is not None or height_id is None:
                return

        await db.execute(delete(StepPole).where(StepPole.calculation_case_id == case.id))
        case.evaluated_positions_m = None
        if height_id is None:
            return
        height = await CalculationCaseRepository.get_height_for_calculation(db, height_id)
        if height is None:
            return
        for step_pole in height.step_poles:
            db.add(StepPole(
                calculation_case_id=case.id,
                material_id=step_pole.material_id,
                name=step_pole.name,
                pole_type=step_pole.pole_type,
                top_elevation_m=step_pole.top_elevation_m,
                diameter_lower_mm=step_pole.diameter_lower_mm,
                diameter_upper_mm=step_pole.diameter_upper_mm,
                thickness_lower_mm=step_pole.thickness_lower_mm,
                thickness_upper_mm=step_pole.thickness_upper_mm,
                quantity=1,
            ))
        if height.evaluated_positions_m is not None:
            case.evaluated_positions_m = list(height.evaluated_positions_m)

    # ===== Simpan (G15), bagian input =====
    @staticmethod
    async def save_input(
        db: AsyncSession, case: CalculationCase, height: PoleStandardHeight, data,
        ground_position: GroundPosition,
    ) -> None:
        """Simpan isian perhitungan tiang standard. Pemanggil sudah mengunci case.
        data: CalculationInput. Objek langsung, kawat, dan lengan ditulis ulang (hapus lalu
        insert). Objek lengan ikut terhapus lewat ON DELETE CASCADE. Draft dikosongkan:
        isiannya kini tersimpan."""
        previous_height_id = case.pole_standard_height_id
        case.pole_standard_id = height.pole_standard_id
        case.pole_standard_height_id = height.id
        case.pole_family = PoleFamily.taper
        case.ground_position = ground_position
        case.embedment_length_mm = data.embedment_length_mm
        case.input_saved_at = datetime.now(timezone.utc)
        case.input_draft = None
        case.input_draft_saved_at = None
        # Tidak diterima dari body: Calculation Service memakai 1. Nilai lama dikosongkan
        # supaya case tidak menampilkan faktor yang tidak dipakai run.
        case.overdesign_factor = None
        await CalculationCaseRepository._sync_catalog_geometry(
            db, case, previous_height_id=previous_height_id, force=data.recopy_catalog,
        )
        
        await db.execute(delete(DirectObject).where(DirectObject.calculation_case_id == case.id))
        for obj in data.direct_objects:
            db.add(DirectObject(calculation_case_id=case.id, **obj.model_dump()))

        await db.execute(delete(OverheadWire).where(OverheadWire.calculation_case_id == case.id))
        for wire in data.overhead_wires:
            db.add(OverheadWire(calculation_case_id=case.id, **wire.model_dump()))

        await db.execute(delete(Arm).where(Arm.calculation_case_id == case.id))
        for arm in data.arms:
            db.add(Arm(
                calculation_case_id=case.id,
                arm_objects=[ArmObject(**obj.model_dump()) for obj in arm.objects],
                **arm.model_dump(exclude={"objects"}),
            ))

        await db.commit()

    # ===== Run =====
    @staticmethod
    async def create_run(
        db: AsyncSession, *, case_id: str, run_by_user_id: str, status: StatusCalculationRun,
        utilization_ratio: float | None, input_snapshot: dict, result_snapshot: dict | None,
        error_snapshot: dict | None,
    ) -> CalculationRun:
        run = CalculationRun(
            calculation_case_id=case_id,
            run_type=CalculationRunType.pole,
            status=status,
            utilization_ratio=utilization_ratio,
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
    async def has_run(db: AsyncSession, case_id: str) -> bool:
        """Termasuk run failed: run tetap riwayat case."""
        stmt = select(exists().where(CalculationRun.calculation_case_id == case_id))
        return bool(await db.scalar(stmt))

    @staticmethod
    async def latest_run(db: AsyncSession, case_id: str) -> CalculationRun | None:
        """Run terbaru case: run_at terbaru, id sebagai penentu bila sama. Termasuk run failed."""
        stmt = (
            select(CalculationRun)
            .where(CalculationRun.calculation_case_id == case_id)
            .order_by(CalculationRun.run_at.desc(), CalculationRun.id)
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    # ===== Draft isian =====
    @staticmethod
    async def put_draft(db: AsyncSession, case: CalculationCase, draft: dict) -> None:
        case.input_draft = draft
        case.input_draft_saved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(case)

    @staticmethod
    async def delete_draft(db: AsyncSession, case: CalculationCase) -> None:
        case.input_draft = None
        case.input_draft_saved_at = None
        await db.commit()


# Field kode header dan master yang dirujuknya.
_REPORT_CODE_FIELDS = (
    ("region_code_id", RegionCode),
    ("department_code_id", DepartmentCode),
    ("author_code_id", AuthorCode),
)


class ReportHeaderRepository:
    """Header laporan: satu per calculation case (tabel reports)."""

    @staticmethod
    async def get(db: AsyncSession, case_id: str) -> Report | None:
        stmt = (
            select(Report)
            .where(Report.calculation_case_id == case_id)
            .options(
                selectinload(Report.region_code),
                selectinload(Report.department_code),
                selectinload(Report.author_code),
            )
            .execution_options(populate_existing=True)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def inactive_code_fields(db: AsyncSession, data: dict) -> list[str]:
        """Field kode yang terisi tetapi tidak menunjuk kode master yang aktif."""
        invalid = []
        for field, model in _REPORT_CODE_FIELDS:
            if data[field] is None:
                continue
            stmt = select(exists().where(model.id == data[field], model.is_active == True))
            if not await db.scalar(stmt):
                invalid.append(field)
        return invalid

    @staticmethod
    async def put(db: AsyncSession, case_id: str, data: dict) -> tuple[Report, bool]:
        """Buat atau ganti seluruh header. Pemanggil sudah mengunci baris case (for_update),
        jadi dua PUT bersamaan diantrikan dan tidak sama-sama meng-insert."""
        header = (await db.execute(
            select(Report).where(Report.calculation_case_id == case_id)
        )).scalar_one_or_none()
        created = header is None
        if created:
            header = Report(calculation_case_id=case_id)
            db.add(header)
        for field, value in data.items():
            setattr(header, field, value)
        await db.commit()
        return await ReportHeaderRepository.get(db, case_id), created
from datetime import datetime

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.intake import Request
from app.database.models.workflow import (
    DeliverableSubtype,
    EventType,
    FileRole,
    FileVersion,
    LifecycleStatus,
    RefKind,
    RequestEvent,
    RequestFile,
    RevisionRound,
    WorkType,
)
from app.modules.case.tables import CASE_FILE_FK



class FileRepository:

    # ===== Baca =====
    @staticmethod
    async def get_in_request(
        db: AsyncSession, request_id: str, file_id: str, *, refresh: bool = False,
    ) -> RequestFile | None:
        """refresh membaca ulang versi dari DB, dipakai sesudah baris request dikunci."""
        stmt = (
            select(RequestFile)
            .where(RequestFile.id == file_id, RequestFile.request_id == request_id)
            .options(selectinload(RequestFile.versions))
        )
        if refresh:
            stmt = stmt.execution_options(populate_existing=True)
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def list_in_request(
        db: AsyncSession,
        request_id: str,
        *,
        file_role: FileRole | None = None,
        work_type: WorkType | None = None,
        case_id: str | None = None,
    ) -> list[RequestFile]:
        """Urut waktu dibuat. work_type dan case_id menyaring deliverable menurut case induknya."""
        stmt = (
            select(RequestFile)
            .where(RequestFile.request_id == request_id)
            .options(selectinload(RequestFile.versions))
            .order_by(RequestFile.created_at, RequestFile.id)
        )
        if file_role is not None:
            stmt = stmt.where(RequestFile.file_role == file_role)
        if work_type is not None:
            column = CASE_FILE_FK[work_type]
            stmt = stmt.where(column == case_id if case_id is not None else column.is_not(None))
        elif case_id is not None:
            stmt = stmt.where(
                (RequestFile.calculation_case_id == case_id) | (RequestFile.drawing_case_id == case_id)
            )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def last_submit_at(db: AsyncSession, request_id: str) -> datetime | None:
        """Waktu submit terakhir: batas versi deliverable yang boleh dilihat yoshimoto_reviewer."""
        return await db.scalar(
            select(func.max(RequestEvent.occurred_at)).where(
                RequestEvent.request_id == request_id,
                RequestEvent.event_type == EventType.submit,
            )
        )

    @staticmethod
    async def request_level_event_ids(db: AsyncSession, event_ids: list[str]) -> set[str]:
        """Dari daftar peristiwa, yang tingkat request (case_id kosong)."""
        if not event_ids:
            return set()
        rows = await db.scalars(
            select(RequestEvent.id).where(RequestEvent.id.in_(event_ids), RequestEvent.case_id.is_(None))
        )
        return set(rows.all())

    @staticmethod
    async def events_in_request(db: AsyncSession, request_id: str, event_ids: list[str]) -> list[RequestEvent]:
        rows = await db.scalars(
            select(RequestEvent).where(RequestEvent.id.in_(event_ids), RequestEvent.request_id == request_id)
        )
        return list(rows.all())


    @staticmethod
    def cover_clause():
        """Kondisi SQL 'request ini punya berkas reference jenis request_cover'.
        Berkorelasi ke Request.id, dipakai di WHERE query daftar request (invariant intake 6)."""
        return exists().where(
            RequestFile.request_id == Request.id,
            RequestFile.file_role == FileRole.reference,
            RequestFile.ref_kind == RefKind.request_cover,
        )

    @staticmethod
    async def storage_refs_for_request(db: AsyncSession, request_id: str) -> list[str]:
        """Seluruh objek storage milik request, dibaca sebelum request dihapus."""
        own = await db.scalars(
            select(RequestFile.storage_ref).where(
                RequestFile.request_id == request_id, RequestFile.storage_ref.is_not(None),
            )
        )
        versioned = await db.scalars(
            select(FileVersion.storage_ref)
            .join(RequestFile, RequestFile.id == FileVersion.request_file_id)
            .where(RequestFile.request_id == request_id, FileVersion.storage_ref.is_not(None))
        )
        return [*own.all(), *versioned.all()]
    
    @staticmethod
    async def storage_refs_for_case(db: AsyncSession, work_type: WorkType, case_id: str) -> list[str]:
        """Objek storage deliverable sebuah case, dibaca sebelum case dihapus."""
        rows = await db.scalars(
            select(FileVersion.storage_ref)
            .join(RequestFile, RequestFile.id == FileVersion.request_file_id)
            .where(CASE_FILE_FK[work_type] == case_id, FileVersion.storage_ref.is_not(None))
        )
        return list(rows.all())

    @staticmethod
    async def latest_round_id(db: AsyncSession, request_id: str) -> str | None:
        """Putaran revisi terbaru dari asal mana pun: putaran yang melahirkan versi baru
        Kosong sebelum putaran pertama."""
        return await db.scalar(
            select(RevisionRound.id)
            .where(RevisionRound.request_id == request_id)
            .order_by(RevisionRound.round_number.desc())
            .limit(1)
        )

    # ===== Tulis =====
    @staticmethod
    async def create_unversioned(
        db: AsyncSession,
        *,
        request_id: str,
        uploader_id: str,
        file_role: FileRole,
        file_name: str,
        storage_ref: str,
        ref_kind: RefKind | None = None,
        request_event_id: str | None = None,
    ) -> RequestFile:
        """Role tidak berversi: lokasi fisik di request_files.storage_ref (invariant berkas 5)."""
        row = RequestFile(
            request_id=request_id,
            uploaded_by_user_id=uploader_id,
            file_role=file_role,
            ref_kind=ref_kind,
            request_event_id=request_event_id,
            file_name=file_name,
            storage_ref=storage_ref,
        )
        db.add(row)
        await db.commit()
        return await FileRepository.get_in_request(db, request_id, row.id, refresh=True)

    @staticmethod
    async def create_versioned(
        db: AsyncSession,
        *,
        request_id: str,
        uploader_id: str,
        file_role: FileRole,
        file_name: str,
        storage_ref: str,
        calculation_case_id: str | None = None,
        drawing_case_id: str | None = None,
        deliverable_subtype: DeliverableSubtype | None = None,
    ) -> RequestFile:
        """Satu transaksi: identitas berkas dan versi pertamanya. Lokasi fisik dicatat di versi,
        request_files.storage_ref dibiarkan kosong (invariant berkas 5)."""
        row = RequestFile(
            request_id=request_id,
            uploaded_by_user_id=uploader_id,
            file_role=file_role,
            calculation_case_id=calculation_case_id,
            drawing_case_id=drawing_case_id,
            deliverable_subtype=deliverable_subtype,
            file_name=file_name,
        )
        db.add(row)
        await db.flush()
        db.add(FileVersion(
            request_file_id=row.id,
            revision_round_id=await FileRepository.latest_round_id(db, request_id),
            version_no=1,
            lifecycle_status=LifecycleStatus.active,
            storage_ref=storage_ref,
            uploaded_by_user_id=uploader_id,
        ))
        await db.commit()
        return await FileRepository.get_in_request(db, request_id, row.id, refresh=True)

    @staticmethod
    async def add_version(
        db: AsyncSession, f: RequestFile, previous: FileVersion, *, uploader_id: str, storage_ref: str,
    ) -> RequestFile:
        """Satu transaksi: versi sebelumnya menjadi obsolete, versi baru aktif dan menunjuknya.
        Pemanggil wajib sudah mengunci request dan memastikan previous masih aktif."""
        previous.lifecycle_status = LifecycleStatus.obsolete
        # Flush dulu: unique partial index hanya mengizinkan satu versi aktif per berkas.
        await db.flush()
        db.add(FileVersion(
            request_file_id=f.id,
            revision_round_id=await FileRepository.latest_round_id(db, f.request_id),
            version_no=max(v.version_no for v in f.versions) + 1,
            lifecycle_status=LifecycleStatus.active,
            previous_version_id=previous.id,
            storage_ref=storage_ref,
            uploaded_by_user_id=uploader_id,
        ))
        await db.commit()
        return await FileRepository.get_in_request(db, f.request_id, f.id, refresh=True)
    
    @staticmethod
    async def create_check_results(
        db: AsyncSession,
        *,
        request_id: str,
        uploader_id: str,
        check_event_ids: list[str],
        file_name: str,
        storage_ref: str,
    ) -> list[RequestFile]:
        """Satu berkas hasil pemeriksaan yang mencakup beberapa case: satu baris per peristiwa
        check, semuanya menunjuk objek yang sama. Penunjuk case
        dibiarkan kosong; case-nya terbaca dari peristiwa yang ditempeli."""
        rows = [
            RequestFile(
                request_id=request_id,
                uploaded_by_user_id=uploader_id,
                file_role=FileRole.check_result,
                request_event_id=event_id,
                file_name=file_name,
                storage_ref=storage_ref,
            )
            for event_id in check_event_ids
        ]
        db.add_all(rows)
        await db.commit()
        return [await FileRepository.get_in_request(db, request_id, row.id, refresh=True) for row in rows]
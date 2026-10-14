from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.intake import Request
from app.database.models.workflow import (
    ChecklistItemStatus,
    NcChecklist,
    NcChecklistItem,
    NcChecklistItemMaster,
    RevisionRound,
    WorkType,
)
from app.modules.assignment.permissions import WORK_TYPES_OF
from app.modules.workflow.gate import apply_prevention_status

_MASTER_EDITABLE = ("step", "item", "sort_order", "is_active")
_ITEM_EDITABLE = ("item_status", "start_at", "finish_at", "duration_minutes", "notes")



# ===== Daftar induk =====
class MasterItemRepository:

    @staticmethod
    async def list_items(
        db: AsyncSession, *, work_type: WorkType | None = None, include_inactive: bool = False,
    ) -> list[NcChecklistItemMaster]:
        stmt = select(NcChecklistItemMaster)
        if work_type is not None:
            stmt = stmt.where(NcChecklistItemMaster.work_type == work_type)
        if not include_inactive:
            stmt = stmt.where(NcChecklistItemMaster.is_active.is_(True))
        stmt = stmt.order_by(
            NcChecklistItemMaster.work_type,
            NcChecklistItemMaster.sort_order,
            NcChecklistItemMaster.created_at,
            NcChecklistItemMaster.id,
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get(db: AsyncSession, master_id: str) -> NcChecklistItemMaster | None:
        return await db.scalar(select(NcChecklistItemMaster).where(NcChecklistItemMaster.id == master_id))

    @staticmethod
    async def create(db: AsyncSession, data: dict) -> NcChecklistItemMaster:
        row = NcChecklistItemMaster(**data)
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def update(db: AsyncSession, row: NcChecklistItemMaster, data: dict) -> NcChecklistItemMaster:
        for field in _MASTER_EDITABLE:
            if field in data:
                setattr(row, field, data[field])
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def work_types_without_active(db: AsyncSession, work_types) -> list[WorkType]:
        """Work type yang belum punya satu pun item master aktif. Checklist tanpa item untuk
        sebuah work type akan lolos gerbang tanpa pemeriksaan work type itu."""
        missing = []
        for work_type in work_types:
            found = await db.scalar(
                select(NcChecklistItemMaster.id).where(
                    NcChecklistItemMaster.work_type == work_type,
                    NcChecklistItemMaster.is_active.is_(True),
                ).limit(1)
            )
            if found is None:
                missing.append(work_type)
        return missing



# ===== Checklist =====
class ChecklistRepository:

    @staticmethod
    async def list_for_request(db: AsyncSession, request_id: str) -> list[NcChecklist]:
        """Semua checklist request, siklus pertama dulu lalu urut nomor putaran Jepang."""
        stmt = (
            select(NcChecklist)
            .outerjoin(RevisionRound, RevisionRound.id == NcChecklist.revision_round_id)
            .where(NcChecklist.request_id == request_id)
            .order_by(RevisionRound.round_number.asc().nulls_first())
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_in_request(db: AsyncSession, request_id: str, checklist_id: str) -> NcChecklist | None:
        return await db.scalar(
            select(NcChecklist).where(NcChecklist.id == checklist_id, NcChecklist.request_id == request_id)
        )

    @staticmethod
    async def items_of(db: AsyncSession, checklist_ids: list[str]) -> dict[str, list[NcChecklistItem]]:
        """Item per checklist, urut work type (calculation dulu), lalu sort_order salinan master."""
        result: dict[str, list[NcChecklistItem]] = {cid: [] for cid in checklist_ids}
        if not checklist_ids:
            return result
        stmt = (
            select(NcChecklistItem)
            .where(NcChecklistItem.nc_checklist_id.in_(checklist_ids))
            .order_by(NcChecklistItem.work_type, NcChecklistItem.sort_order, NcChecklistItem.step, NcChecklistItem.id)
        )
        for item in (await db.execute(stmt)).scalars().all():
            result[item.nc_checklist_id].append(item)
        return result

    @staticmethod
    async def get_item(db: AsyncSession, checklist_id: str, item_id: str) -> NcChecklistItem | None:
        return await db.scalar(
            select(NcChecklistItem).where(NcChecklistItem.id == item_id, NcChecklistItem.nc_checklist_id == checklist_id)
        )

    @staticmethod
    async def _copy_items(db: AsyncSession, checklist_id: str, work_types) -> None:
        """G6: salin item master aktif. step, item, work_type, dan sort_order disalin;
        sesudah ini item tidak pernah membaca master lagi (larangan 18)."""
        for work_type in work_types:
            masters = await MasterItemRepository.list_items(db, work_type=work_type)
            for master in masters:
                db.add(NcChecklistItem(
                    nc_checklist_id=checklist_id,
                    source_master_id=master.id,
                    work_type=master.work_type,
                    step=master.step,
                    item=master.item,
                    sort_order=master.sort_order,
                    item_status=ChecklistItemStatus.pending,
                ))

    @staticmethod
    async def create_for_cycle(db: AsyncSession, req: Request, revision_round_id: str | None) -> NcChecklist:
        """Satu transaksi: checklist siklus berjalan + salinan item untuk work type di design_type,
        lalu status prevention_check dihitung ulang. Pemanggil wajib sudah mengunci req."""
        checklist = NcChecklist(request_id=req.id, revision_round_id=revision_round_id)
        db.add(checklist)
        await db.flush()
        await ChecklistRepository._copy_items(db, checklist.id, WORK_TYPES_OF[req.design_type])
        await db.flush()
        await apply_prevention_status(db, req)
        await db.commit()
        await db.refresh(checklist)
        return checklist

    @staticmethod
    async def missing_work_types(db: AsyncSession, checklist: NcChecklist, work_types) -> list[WorkType]:
        """Work type yang belum punya satu pun item di checklist ini."""
        present = set((await db.execute(
            select(NcChecklistItem.work_type).where(NcChecklistItem.nc_checklist_id == checklist.id).distinct()
        )).scalars().all())
        return [wt for wt in work_types if wt not in present]

    @staticmethod
    async def add_missing_work_types(db: AsyncSession, checklist: NcChecklist, work_types) -> None:
        """designType melebar di tengah siklus: salin item work type yang belum ada di checklist.
        Item work type yang hilang dari designType dibiarkan (checker menandainya not_applicable).
        Tidak commit; dipanggil di dalam transaksi update request."""
        missing = await ChecklistRepository.missing_work_types(db, checklist, work_types)
        await ChecklistRepository._copy_items(db, checklist.id, missing)

    @staticmethod
    async def update_item(db: AsyncSession, item: NcChecklistItem, data: dict, *, actor_id: str) -> NcChecklistItem:
        for field in _ITEM_EDITABLE:
            if field in data:
                setattr(item, field, data[field])
        if "item_status" in data:
            # Pemeriksa hidup di tingkat item: yang menetapkan status akhir.
            item.reviewed_by = None if item.item_status == ChecklistItemStatus.pending else actor_id
        if "duration_minutes" not in data and item.start_at is not None and item.finish_at is not None:
            # Dihitung dari waktu mulai dan selesai, kecuali diisi manual di permintaan yang sama.
            item.duration_minutes = round((item.finish_at - item.start_at).total_seconds() / 60)
        await db.commit()
        await db.refresh(item)
        return item

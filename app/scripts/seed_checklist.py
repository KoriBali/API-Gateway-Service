"""
Seed CONTOH daftar induk NC Prevention Checklist (nc_checklist_item_masters).

Isi asli daftar induk per work type belum diterima dari stakeholder (butir R-3). Item di sini
hanya contoh supaya checklist bisa dibuat dan diuji. Semua teks diawali "[Contoh]", supaya
checklist yang menyalinnya mudah dikenali. Isi asli dimasukkan superadmin lewat
POST /api/nc-checklist-item-masters, lalu item contoh dinonaktifkan (isActive false).

How to Run (pipenv shell):
    python -m app.scripts.seed_checklist

Prasyarat: migration di head.
- Idempotent: item dengan work_type, step, dan item yang sama tidak dibuat ulang.
"""
import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.database.models.workflow import NcChecklistItemMaster, WorkType

# (work_type, sort_order, step, item)
MASTER_ITEMS = [
    (WorkType.calculation, 10, "[Contoh] Input", "[Contoh] Kondisi desain sama dengan cover request"),
    (WorkType.calculation, 20, "[Contoh] Input", "[Contoh] Data tiang dan objek beban lengkap"),
    (WorkType.calculation, 30, "[Contoh] Hasil", "[Contoh] Seluruh safety factor memenuhi syarat"),
    (WorkType.calculation, 40, "[Contoh] Laporan", "[Contoh] Header laporan perhitungan sesuai request"),
    (WorkType.drawing, 10, "[Contoh] Ukuran", "[Contoh] Ukuran gambar sama dengan hasil perhitungan"),
    (WorkType.drawing, 20, "[Contoh] Lembar", "[Contoh] Nomor gambar dan nomor lembar terisi"),
    (WorkType.drawing, 30, "[Contoh] Lembar", "[Contoh] Kop gambar sesuai tipe drawing"),
]


async def _seed_masters(db) -> int:
    created = 0
    for work_type, sort_order, step, item in MASTER_ITEMS:
        exists = await db.scalar(
            select(NcChecklistItemMaster.id).where(
                NcChecklistItemMaster.work_type == work_type,
                NcChecklistItemMaster.step == step,
                NcChecklistItemMaster.item == item,
            )
        )
        if exists is not None:
            continue
        db.add(NcChecklistItemMaster(work_type=work_type, step=step, item=item, sort_order=sort_order))
        created += 1
    return created


async def main():
    async with AsyncSessionLocal() as db:
        created = await _seed_masters(db)
        await db.commit()
    print(f"Seed checklist selesai. Item master contoh: {created} dibuat.")


if __name__ == "__main__":
    asyncio.run(main())
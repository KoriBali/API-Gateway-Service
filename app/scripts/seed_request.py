"""
File ini untuk inisiasi Data awal (seeding) Data Request.

Prasyarat (jalankan lebih dulu):
    python -m app.scripts.seed_identity   # user + department
    python -m app.scripts.seed_master     # pole_categories dll

How to Run(pipenv shell):
    python -m app.scripts.seed_request

Catatan desain:
- responsible_department_id SELALU mengikuti department si pembuat (created_by_user),
  sesuai aturan create_request di router (department dikunci ke pembuat).
- Idempotent: baris di-skip bila sudah ada request dengan
  (created_by_user_id, request_no, status) yang sama.
- Data sengaja tersebar ke beberapa drafter & department dengan status beragam
  agar logic scoping (superadmin/admin/drafter) dan alur submit/clone/supersede
  bisa diuji secara nyata.
"""
import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.database.models.identity import (
    User,
    Request,
    RequestStatus,
    RequestType,
    DesignType,
    RequestCategory,
    PoleKind,
)
from app.database.models.master import PoleCategory


_TODAY = date.today()


def _due(days: int | None) -> date | None:
    return None if days is None else _TODAY + timedelta(days=days)


# Request mandiri (tanpa relasi supersede).
# creator = username pembuat; pole_category = nama kategori (lihat seed_master).
STANDALONE_REQUESTS = [
    # budi (drafter/YSG)
    {
        "creator": "budi", "pole_category": "lighting-pole",
        "request_no": "REQ-2026-001", "receipt_no": "RCP-001", "pj_no": "PJ-001",
        "request_type": RequestType.generally, "design_type": DesignType.drawing,
        "request_category": RequestCategory.new, "pole_kind": PoleKind.standard,
        "company_name": "PT Cahaya Abadi", "project_name": "Pemasangan Tiang Jl. Merdeka",
        "due_in_days": 14, "status": RequestStatus.draft,
    },
    {
        # submitted -> dipakai untuk uji CLONE
        "creator": "budi", "pole_category": "acemast",
        "request_no": "REQ-2026-002", "receipt_no": "RCP-002", "pj_no": "PJ-002",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_category": RequestCategory.revision, "pole_kind": PoleKind.custom,
        "company_name": "PT Sinar Jaya", "project_name": "Revisi Struktur Menara",
        "due_in_days": 30, "status": RequestStatus.submitted,
    },
    # andi (drafter/YSG) -> menguji isolasi antar-drafter dalam department yang sama
    {
        "creator": "andi", "pole_category": "signboard",
        "request_no": "REQ-2026-003", "receipt_no": "RCP-003", "pj_no": "PJ-003",
        "request_type": RequestType.generally, "design_type": DesignType.drawing_calculation,
        "request_category": RequestCategory.modification, "pole_kind": PoleKind.standard,
        "company_name": "CV Mandiri", "project_name": "Papan Reklame Sudirman",
        "due_in_days": 7, "status": RequestStatus.draft,
    },
    # dewi (drafter/YSC) -> department berbeda, menguji scope lintas-department
    {
        "creator": "dewi", "pole_category": "lighting-pole",
        "request_no": "REQ-2026-004", "receipt_no": "RCP-004", "pj_no": "PJ-004",
        "request_type": RequestType.special, "design_type": DesignType.calculation,
        "request_category": RequestCategory.replacement, "pole_kind": PoleKind.custom,
        "company_name": "PT Nusantara", "project_name": "Penggantian Tiang Lama",
        "due_in_days": 21, "status": RequestStatus.submitted,
    },
    {
        # semua field opsional kosong -> menguji nullable (pole_kind/company/project/due_date)
        "creator": "dewi", "pole_category": "multiple",
        "request_no": "REQ-2026-005", "receipt_no": "RCP-005", "pj_no": "PJ-005",
        "request_type": RequestType.generally, "design_type": DesignType.drawing,
        "request_category": RequestCategory.new, "pole_kind": None,
        "company_name": None, "project_name": None,
        "due_in_days": None, "status": RequestStatus.draft,
    },
    # eko (drafter/YSF)
    {
        "creator": "eko", "pole_category": "acemast",
        "request_no": "REQ-2026-006", "receipt_no": "RCP-006", "pj_no": "PJ-006",
        "request_type": RequestType.generally, "design_type": DesignType.calculation,
        "request_category": RequestCategory.new, "pole_kind": PoleKind.standard,
        "company_name": "PT Bumi Persada", "project_name": "Menara Transmisi A",
        "due_in_days": 45, "status": RequestStatus.draft,
    },
]


# Rantai supersede: request lama (superseded) digantikan request baru (draft)
# dengan ketiga nomor identik di department yang sama (skenario nyata supersede).
SUPERSEDE_CHAIN = {
    "creator": "eko", "pole_category": "lighting-pole",
    "request_no": "REQ-2026-007", "receipt_no": "RCP-007", "pj_no": "PJ-007",
    "request_type": RequestType.generally, "design_type": DesignType.drawing,
    "request_category": RequestCategory.new, "pole_kind": PoleKind.standard,
    "company_name": "PT Terang",
    "due_in_days": 10,
    "old_project_name": "Tiang Lampu Taman - v1",
    "new_project_name": "Tiang Lampu Taman - v2",
}


async def _load_lookups(db) -> tuple[dict[str, User], dict[str, str]]:
    users = {u.username: u for u in (await db.execute(select(User))).scalars().all()}
    categories = {
        c.name: c.id for c in (await db.execute(select(PoleCategory))).scalars().all()
    }
    return users, categories


async def _find_existing(db, *, user_id: str, request_no: str, status: RequestStatus) -> Request | None:
    stmt = select(Request).where(
        Request.created_by_user_id == user_id,
        Request.request_no == request_no,
        Request.status == status,
    )
    return (await db.execute(stmt)).scalars().first()


def _resolve(spec: dict, users: dict[str, User], categories: dict[str, str]) -> tuple[User, str]:
    user = users.get(spec["creator"])
    if user is None:
        raise ValueError(
            f"User '{spec['creator']}' tidak ada. Jalankan seed_identity dulu."
        )
    if user.department_id is None:
        raise ValueError(
            f"User '{spec['creator']}' tidak punya department; tidak bisa jadi pembuat request."
        )
    category_id = categories.get(spec["pole_category"])
    if category_id is None:
        raise ValueError(
            f"Pole category '{spec['pole_category']}' tidak ada. Jalankan seed_master dulu."
        )
    return user, category_id


async def _seed_standalone(db, users, categories) -> int:
    created = 0
    for spec in STANDALONE_REQUESTS:
        user, category_id = _resolve(spec, users, categories)

        if await _find_existing(db, user_id=user.id, request_no=spec["request_no"], status=spec["status"]):
            continue

        db.add(Request(
            responsible_department_id=user.department_id,
            created_by_user_id=user.id,
            pole_category_id=category_id,
            request_no=spec["request_no"],
            receipt_no=spec["receipt_no"],
            pj_no=spec["pj_no"],
            request_type=spec["request_type"],
            design_type=spec["design_type"],
            request_category=spec["request_category"],
            pole_kind=spec["pole_kind"],
            company_name=spec["company_name"],
            project_name=spec["project_name"],
            due_date=_due(spec["due_in_days"]),
            status=spec["status"],
        ))
        created += 1
    return created


async def _seed_supersede_chain(db, users, categories) -> int:
    spec = SUPERSEDE_CHAIN
    user, category_id = _resolve(spec, users, categories)

    # Request lama sudah pernah dibuat? -> anggap rantai sudah di-seed.
    if await _find_existing(db, user_id=user.id, request_no=spec["request_no"], status=RequestStatus.superseded):
        return 0

    common = dict(
        responsible_department_id=user.department_id,
        created_by_user_id=user.id,
        pole_category_id=category_id,
        request_no=spec["request_no"],
        receipt_no=spec["receipt_no"],
        pj_no=spec["pj_no"],
        request_type=spec["request_type"],
        design_type=spec["design_type"],
        request_category=spec["request_category"],
        pole_kind=spec["pole_kind"],
        company_name=spec["company_name"],
        due_date=_due(spec["due_in_days"]),
    )

    old_req = Request(**common, project_name=spec["old_project_name"], status=RequestStatus.superseded)
    db.add(old_req)
    await db.flush()  # butuh old_req.id untuk ditunjuk request baru

    new_req = Request(
        **common,
        project_name=spec["new_project_name"],
        status=RequestStatus.draft,
        supersedes_request_id=old_req.id,
    )
    db.add(new_req)
    return 2


async def main():
    async with AsyncSessionLocal() as db:
        users, categories = await _load_lookups(db)
        standalone = await _seed_standalone(db, users, categories)
        chain = await _seed_supersede_chain(db, users, categories)
        await db.commit()
    print(
        f"Seed request selesai. Standalone: {standalone} dibuat, "
        f"Supersede chain: {chain} baris dibuat."
    )


if __name__ == "__main__":
    asyncio.run(main())

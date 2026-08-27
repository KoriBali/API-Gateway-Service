"""
File ini untuk inisiasi Data awal (seeding) Data Identity

How to Run(pipenv shell):
    python -m app.scripts.seed_identity
"""
import asyncio

from sqlalchemy import select, or_

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.database.models import User, Department
from app.database.models.identity import Role


DEPARTMENTS = [
    ("YSG", "North Kanto Sales Office"),
    ("YSC", "Tokyo Sales Office"),
    ("YSF", "Nagano Sales Office"),
    ("YSJ", "Kyushu Branch"),
    ("YS" , "Head Office"),
]

EMPLOYEES = [
    {"username": "budi", "email": "budi@corp.id", "full_name": "Budi Santoso", "role": "drafter", "department_code": "YSG"},
    {"username": "sari", "email": "sari@corp.id", "full_name": "Sari Dewi",    "role": "admin",   "department_code": "YSG"},
]


async def _seed_departments(db) -> dict[str, str]:
    code_to_id: dict[str, str] = {}
    for code, name in DEPARTMENTS:
        existing = await db.execute(
            select(Department).where(Department.code == code)
        )
        dept = existing.scalar_one_or_none()

        if dept is None:
            dept = Department(code=code, name=name)
            db.add(dept)
            await db.flush()

        code_to_id[code] = dept.id
    return code_to_id


async def _seed_employees(db, dept_map: dict[str, str]) -> int:
    created = 0
    for emp in EMPLOYEES:
        existing = await db.execute(
            select(User).where(or_(User.username == emp["username"], User.email == emp["email"]))
        )
        if existing.scalar_one_or_none() is not None:
            continue

        dept_id = dept_map.get(emp["department_code"])
        if dept_id is None:
            raise ValueError(
                f"Department code '{emp['department_code']}' untuk user '{emp['username']}' "
                f"tidak ada di DEPARTMENTS. Perbaiki data seed."
            )

        db.add(User(
            username=emp["username"],
            email=emp["email"],
            full_name=emp["full_name"],
            password_hash=hash_password(settings.SEED_DEFAULT_USER_PASSWORD),
            role=Role(emp["role"]),
            department_id=dept_id,      
            is_active=True,
            is_verified=True,
        ))
        created += 1
    return created


async def _seed_superadmin(db) -> str:
    username = settings.SEED_SUPERADMIN_USERNAME
    email = settings.SEED_SUPERADMIN_EMAIL

    existing = await db.execute(
        select(User).where(or_(User.username == username, User.email == email))
    )
    if existing.scalar_one_or_none() is not None:
        return "exists"

    db.add(User(
        username=username,
        email=email,
        full_name=settings.SEED_SUPERADMIN_FULL_NAME,
        password_hash=hash_password(settings.SEED_SUPERADMIN_PASSWORD),
        role=Role.superadmin,
        department_id=None,     
        is_active=True,
        is_verified=True,
    ))
    return "created"


async def main():
    async with AsyncSessionLocal() as db:
        dept_map = await _seed_departments(db)
        status = await _seed_superadmin(db)
        employee_count = await _seed_employees(db, dept_map)
        await db.commit()
    print(f"Seed identity selesai. Departments: {len(dept_map)}, "
      f"Superadmin: {status}, Employees: {employee_count} dibuat.")


if __name__ == "__main__":
    asyncio.run(main())

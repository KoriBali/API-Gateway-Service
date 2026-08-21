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
from app.database.models import User
from app.database.models.identity import Role


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
        department_id=None,      # tanpa department → aman dari CASCADE
        is_active=True,
        is_verified=True,
    ))
    return "created"


async def main():
    async with AsyncSessionLocal() as db:
        status = await _seed_superadmin(db)
        await db.commit()
    print(f"Seed identity selesai. Superadmin: {status}.")


if __name__ == "__main__":
    asyncio.run(main())

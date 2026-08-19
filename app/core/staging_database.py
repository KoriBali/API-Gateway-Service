from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy import event
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# DATABASE_URL = "sqlite+aiosqlite:///./gateway.db"

# Async Engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False
)

# Tidak dibutuhkan karena sudah tidak menggunakan PostgreSQL
# @event.listens_for(engine.sync_engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     cursor = dbapi_connection.cursor()
#     cursor.execute("PRAGMA foreign_keys=ON")
#     cursor.close()


# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Base ORM Model
class Base(DeclarativeBase):
    pass


# Dependency Injection
async def get_db():

    async with AsyncSessionLocal() as session:
        yield session
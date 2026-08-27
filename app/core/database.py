from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings, build_async_db_url_and_connect_args

# DATABASE_URL = "sqlite+aiosqlite:///./gateway.db"

# Supabase Conf
_db_url, _connect_args = build_async_db_url_and_connect_args(settings.DATABASE_URL)


NAMING_CONVENTION = {
    "ix":  "ix_%(column_0_label)s",
    "uq":  "uq_%(table_name)s_%(column_0_name)s",
    "ck":  "ck_%(table_name)s_%(constraint_name)s",
    "fk":  "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk":  "pk_%(table_name)s",
}


# Async Engine
engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=_connect_args,
    pool_pre_ping=True,   
)


# Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


# Base ORM Model
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)



# Dependency Injection
async def get_db():

    async with AsyncSessionLocal() as session:
        yield session
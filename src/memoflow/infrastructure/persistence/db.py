"""SQLAlchemy 异步引擎 / Session 工厂（SQLite 本地存储）。"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    return create_async_engine(database_url, echo=echo, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def init_models(engine: AsyncEngine) -> None:
    """开发/首次运行时自动建表。生产环境建议使用 Alembic 迁移。"""
    # 确保所有模型都已注册到 Base.metadata
    from memoflow.infrastructure.persistence import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_meetings_table)


def _migrate_meetings_table(connection) -> None:  # noqa: ANN001
    """为已有 SQLite 数据库补充新增列（create_all 不会修改已存在的表）。"""
    from sqlalchemy import inspect, text

    inspector = inspect(connection)
    if "meetings" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("meetings")}
    for column, ddl in (
        ("failed_stage", "ALTER TABLE meetings ADD COLUMN failed_stage VARCHAR"),
        ("resume_status", "ALTER TABLE meetings ADD COLUMN resume_status VARCHAR"),
    ):
        if column not in existing:
            connection.execute(text(ddl))

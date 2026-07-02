from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def ensure_column(
    conn: AsyncConnection, table: str, column: str, add_column_sql: str
) -> None:
    """No formal migration tool (Alembic) yet — fine for a handful of
    additive columns, but revisit that decision once schema changes get more
    frequent than this. `Base.metadata.create_all` only creates missing
    tables; it never alters an existing one, so a column added to a model
    after a real deployment's DB already has that table needs this instead."""

    def _existing_columns(sync_conn) -> set[str]:
        return {c["name"] for c in inspect(sync_conn).get_columns(table)}

    existing = await conn.run_sync(_existing_columns)
    if column not in existing:
        await conn.execute(text(add_column_sql))

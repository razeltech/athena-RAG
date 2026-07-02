"""Create database tables. Run once: python -m scripts.init_db"""
import asyncio

from app.db.database import engine
from app.db.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from bot.config import settings


engine: AsyncEngine = create_async_engine(settings.postgres_dsn, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def check_postgres() -> None:
    async with engine.begin() as connection:
        await connection.exec_driver_sql("SELECT 1")

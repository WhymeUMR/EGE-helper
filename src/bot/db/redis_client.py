from redis.asyncio import Redis

from bot.config import settings


redis_client = Redis.from_url(settings.redis_dsn, decode_responses=True)


async def check_redis() -> None:
    await redis_client.ping()

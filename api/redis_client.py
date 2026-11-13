
from redis.asyncio import Redis

from config import settings


async def create_redis_connection():

    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True
    )

    await client.ping()

    return client


async def close_redis_connection(client):

    await client.aclose()

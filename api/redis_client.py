
from redis.asyncio import Redis

from config import settings


async def create_redis_connection():
    # Create the client without pinging so the API can start while Redis is
    # recovering. The /ready endpoint reports when Redis is reachable.
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


async def close_redis_connection(client):

    await client.aclose()

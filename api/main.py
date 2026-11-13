
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    status
)

from config import settings
from schemas import LogCreate, LogBatch
from redis_client import (
    create_redis_connection,
    close_redis_connection
)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Connexion a Redis au demarrage
    app.state.redis = await create_redis_connection()

    yield

    # Fermeture de Redis a l'arret
    await close_redis_connection(app.state.redis)


app = FastAPI(
    title=settings.app_name,
    description="CloudLog - Distributed Log Analytics API",
    version="1.0.0",
    lifespan=lifespan
)


# 1. Accueil
@app.get("/")
async def home():

    return {
        "message": "Welcome to CloudLog API",
        "version": "1.0.0",
        "status": "running"
    }


# 2. Verification de l'API
@app.get("/health")
async def health():

    return {
        "status": "healthy",
        "service": "cloudlog-api"
    }


# 3. Verification de Redis
@app.get("/ready")
async def readiness(request: Request):

    try:
        await request.app.state.redis.ping()

        return {
            "status": "ready",
            "redis": "connected"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable"
        )


# 4. Reception d'un seul log
@app.post("/logs", status_code=status.HTTP_202_ACCEPTED)
async def receive_log(
    log: LogCreate,
    request: Request
):

    try:
        redis = request.app.state.redis

        log_data = log.model_dump(mode="json")

        await redis.lpush(
            settings.redis_queue,
            __import__("json").dumps(log_data)
        )

        return {
            "event_id": str(log.event_id),
            "status": "accepted",
            "message": "Log added to processing queue"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to enqueue log"
        )


# 5. Reception de plusieurs logs
@app.post("/logs/bulk", status_code=status.HTTP_202_ACCEPTED)
async def receive_bulk_logs(
    batch: LogBatch,
    request: Request
):

    try:
        redis = request.app.state.redis

        pipeline = redis.pipeline(transaction=False)

        for log in batch.logs:

            log_data = log.model_dump(mode="json")

            pipeline.lpush(
                settings.redis_queue,
                __import__("json").dumps(log_data)
            )

        await pipeline.execute()

        return {
            "status": "accepted",
            "received": len(batch.logs),
            "message": "Logs added to processing queue"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to enqueue logs"
        )


# 6. Etat de la file d'attente
@app.get("/queue/status")
async def queue_status(request: Request):

    try:
        redis = request.app.state.redis

        pending = await redis.llen(
            settings.redis_queue
        )

        return {
            "queue": settings.redis_queue,
            "pending_logs": pending,
            "status": "available"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Unable to read queue status"
        )

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status

from config import settings
from redis_client import create_redis_connection, close_redis_connection
from schemas import LogAccepted, LogBatch, LogBatchAccepted, LogCreate


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cloudlog.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CloudLog API")
    app.state.redis = await create_redis_connection()
    try:
        yield
    finally:
        await close_redis_connection(app.state.redis)
        logger.info("Stopped CloudLog API")


app = FastAPI(
    title=settings.app_name,
    description="CloudLog - Distributed Log Analytics API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def home():
    return {"service": settings.app_name, "version": "1.0.0"}


@app.get("/health")
async def health():
    # Liveness only: a Redis outage should not restart a healthy API process.
    return {"status": "healthy", "service": "cloudlog-api"}


@app.get("/ready")
async def readiness(request: Request):
    try:
        await request.app.state.redis.ping()
    except Exception as exc:
        logger.warning("Readiness check failed: Redis is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is unavailable",
        ) from exc
    return {"status": "ready", "redis": "connected"}


@app.post("/logs", status_code=status.HTTP_202_ACCEPTED, response_model=LogAccepted)
async def receive_log(log: LogCreate, request: Request):
    try:
        await request.app.state.redis.lpush(
            settings.redis_queue,
            json.dumps(log.model_dump(mode="json")),
        )
    except Exception as exc:
        logger.exception("Failed to enqueue event %s", log.event_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue log",
        ) from exc

    return {
        "event_id": log.event_id,
        "status": "accepted",
        "queue": settings.redis_queue,
    }


@app.post(
    "/logs/bulk",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=LogBatchAccepted,
)
async def receive_bulk_logs(batch: LogBatch, request: Request):
    try:
        # A transaction prevents a successful response for a partially queued batch.
        pipeline = request.app.state.redis.pipeline(transaction=True)
        for log in batch.logs:
            pipeline.lpush(
                settings.redis_queue,
                json.dumps(log.model_dump(mode="json")),
            )
        await pipeline.execute()
    except Exception as exc:
        logger.exception("Failed to enqueue batch of %d events", len(batch.logs))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue logs",
        ) from exc

    logger.info("Accepted batch of %d events", len(batch.logs))
    return {
        "status": "accepted",
        "accepted_count": len(batch.logs),
        "event_ids": [log.event_id for log in batch.logs],
        "queue": settings.redis_queue,
    }


@app.get("/queue/status")
async def queue_status(request: Request):
    try:
        pending = await request.app.state.redis.llen(settings.redis_queue)
    except Exception as exc:
        logger.exception("Failed to read Redis queue status")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to read queue status",
        ) from exc
    return {
        "queue": settings.redis_queue,
        "pending_logs": pending,
        "status": "available",
    }

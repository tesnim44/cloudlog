import json
import sys
from pathlib import Path
from uuid import uuid4

import anyio
import httpx
import pytest
from httpx import ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.items = []

    def lpush(self, key, value):
        self.items.append((key, value))
        return self

    async def execute(self):
        if self.redis.fail:
            raise ConnectionError("redis unavailable")
        self.redis.items.extend(self.items)
        return [len(self.redis.items)] * len(self.items)


class FakeRedis:
    def __init__(self):
        self.items = []
        self.fail = False

    async def lpush(self, key, value):
        if self.fail:
            raise ConnectionError("redis unavailable")
        self.items.insert(0, (key, value))

    def pipeline(self, transaction=True):
        assert transaction is True
        return FakePipeline(self)

    async def ping(self):
        if self.fail:
            raise ConnectionError("redis unavailable")
        return True

    async def llen(self, key):
        if self.fail:
            raise ConnectionError("redis unavailable")
        return sum(1 for item_key, _ in self.items if item_key == key)

    async def aclose(self):
        pass


class APIClient:
    """Small synchronous wrapper around the ASGI app for stable local tests."""

    async def _send(self, method, path, kwargs):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=main.app),
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    def get(self, path):
        return anyio.run(self._send, "GET", path, {}, backend="asyncio")

    def post(self, path, **kwargs):
        return anyio.run(self._send, "POST", path, kwargs, backend="asyncio")


@pytest.fixture
def client(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(main.app.state, "redis", fake_redis, raising=False)
    test_client = APIClient()
    test_client.fake_redis = fake_redis
    return test_client


def event_payload(**overrides):
    payload = {
        "event_id": str(uuid4()),
        "timestamp": "2026-11-16T06:30:00+01:00",
        "application": "Banking",
        "level": "ERROR",
        "message": "Database connection failed",
        "response_time": 2500,
        "status_code": 500,
    }
    payload.update(overrides)
    return payload


def test_root_and_health_are_available(client):
    assert client.get("/").status_code == 200
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


def test_readiness_reports_redis_availability(client):
    assert client.get("/ready").status_code == 200
    client.fake_redis.fail = True
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Redis is unavailable"


def test_single_log_is_queued_as_canonical_json(client):
    payload = event_payload()
    response = client.post("/logs", json=payload)

    assert response.status_code == 202
    assert response.json() == {
        "event_id": payload["event_id"],
        "status": "accepted",
        "queue": "cloudlog:incoming",
    }
    key, serialized = client.fake_redis.items[0]
    queued = json.loads(serialized)
    assert key == "cloudlog:incoming"
    assert queued["event_id"] == payload["event_id"]
    assert queued["timestamp"] == "2026-11-16T05:30:00Z"
    assert set(queued) == set(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"level": "TRACE"},
        {"response_time": -1},
        {"status_code": 99},
        {"timestamp": "2026-11-16T06:30:00"},
        {"message": "   "},
    ],
)
def test_invalid_event_is_rejected(overrides, client):
    response = client.post("/logs", json=event_payload(**overrides))
    assert response.status_code == 422
    assert client.fake_redis.items == []


def test_bulk_queues_all_events_and_returns_identifiers(client):
    events = [event_payload(), event_payload()]
    response = client.post("/logs/bulk", json={"logs": events})

    assert response.status_code == 202
    assert response.json()["accepted_count"] == 2
    assert response.json()["event_ids"] == [event["event_id"] for event in events]
    assert len(client.fake_redis.items) == 2


@pytest.mark.parametrize("logs", [[], [event_payload()] * 1001])
def test_empty_and_oversized_batches_are_rejected(logs, client):
    response = client.post("/logs/bulk", json={"logs": logs})
    assert response.status_code == 422
    assert client.fake_redis.items == []


def test_redis_failure_never_returns_accepted(client):
    client.fake_redis.fail = True
    response = client.post("/logs", json=event_payload())
    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to enqueue log"


def test_bulk_redis_failure_is_reported_without_partial_success(client):
    client.fake_redis.fail = True
    response = client.post(
        "/logs/bulk",
        json={"logs": [event_payload(), event_payload()]},
    )
    assert response.status_code == 503
    assert client.fake_redis.items == []


def test_queue_status_returns_pending_count(client):
    client.post("/logs", json=event_payload())
    response = client.get("/queue/status")
    assert response.status_code == 200
    assert response.json()["pending_logs"] == 1

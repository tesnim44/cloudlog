# CloudLog API

FastAPI producer for the CloudLog log-processing queue. The API validates each
event and returns `202 Accepted` only after Redis accepts it.

## Run locally

From the repository root, create and activate a Python virtual environment,
install the API dependencies, copy `api/.env.example` to `api/.env`, and start
Redis. Then run:

```powershell
cd api
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

When using a virtual environment created at `api/venv`, activate it with
`.\venv\Scripts\Activate.ps1` instead. Interactive API documentation is at
`http://localhost:8000/docs`.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `CloudLog API` | Service title shown by the API. |
| `REDIS_HOST` | `localhost` | Redis hostname; use `redis` in Compose/Kubernetes. |
| `REDIS_PORT` | `6379` | Redis service port. |
| `REDIS_DB` | `0` | Redis database number. |
| `REDIS_PASSWORD` | unset | Optional Redis password. |
| `REDIS_QUEUE` | `cloudlog:incoming` | Redis List shared with the worker. |
| `API_PORT` | `8000` | Uvicorn/container port. |

The API creates its Redis client during startup without requiring Redis to be
available at that moment. `/health` is a liveness check; `/ready` returns 503
until Redis responds to `PING`. The API Docker image listens on `0.0.0.0` and
runs as the non-root `appuser` account.

## Event and queue contract

Every event has `event_id` (UUID), `timestamp` (ISO 8601 with timezone),
`application` (1-100 characters), `level` (`INFO`, `WARNING`, or `ERROR`),
`message` (1-2,000 characters), `response_time` (0-600,000 milliseconds), and
`status_code` (100-599). Timestamps are normalized to UTC before enqueueing.

The producer writes one UTF-8 JSON object per Redis List item to
`cloudlog:incoming` with `LPUSH`. The matching worker consumes with `BRPOP`.
Bulk requests contain 1-1,000 events and use a Redis transaction.

## Endpoints

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/` | Service name and version. |
| `GET` | `/health` | API liveness. |
| `GET` | `/ready` | Redis readiness. |
| `POST` | `/logs` | Validates and queues one event; returns 202 and `event_id`. |
| `POST` | `/logs/bulk` | Validates and queues a bounded batch; returns 202 and accepted IDs. |
| `GET` | `/queue/status` | Redis queue depth. |

Invalid payloads receive 422. Redis failures receive 503 and never return a
successful acceptance response. A Redis List is a simple queue; PostgreSQL
remains the permanent store for processed records.

## Docker and tests

Build and run the API image with Redis reachable at the configured service
name:

```powershell
docker build -t cloudlog-api:dev .
docker run --rm -p 8000:8000 -e REDIS_HOST=host.docker.internal cloudlog-api:dev
```

Run the automated API tests from the repository root:

```powershell
python -m pytest api/tests -q
```

The tests use a fake Redis client and do not require a personal Redis server.

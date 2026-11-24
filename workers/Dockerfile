FROM python:3.12-slim AS builder
WORKDIR /build
COPY workers/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /install /usr/local
COPY workers/redis_consumer.py workers/worker.py ./workers/

RUN useradd --create-home --uid 10001 appuser
USER appuser

CMD ["python", "-m", "workers.redis_consumer"]
CREATE TABLE IF NOT EXISTS logs (
    id BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    timestamp TIMESTAMPTZ NOT NULL,
    application VARCHAR(100) NOT NULL,
    level VARCHAR(10) NOT NULL CHECK (
        level IN ('INFO', 'WARNING', 'ERROR')
    ),
    message TEXT NOT NULL,
    response_time INTEGER NOT NULL CHECK (response_time >= 0),
    status_code INTEGER NOT NULL CHECK (
        status_code BETWEEN 100 AND 599
    ),
    is_anomaly BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp);
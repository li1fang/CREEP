-- AssetEvent v1.0 storage DDL (append-only)
-- Aligns with schemas/v1.0/AssetEvent.json

CREATE TABLE IF NOT EXISTS asset_events (
    event_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    env TEXT,
    asset_id UUID NOT NULL,
    task_id UUID,
    lease_id UUID,
    correlation_id TEXT,
    causation_id UUID,
    event_type TEXT NOT NULL,
    source TEXT,
    severity TEXT CHECK (severity IN ('DEBUG', 'INFO', 'WARN', 'ERROR')),
    old_status TEXT,
    new_status TEXT,
    message TEXT,
    error_code TEXT,
    error_message TEXT,
    provider_status TEXT,
    http_status INTEGER CHECK (http_status BETWEEN 100 AND 599),
    latency_ms INTEGER CHECK (latency_ms >= 0),
    retryable BOOLEAN,
    occurred_at TIMESTAMPTZ NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    tags TEXT[],
    context JSONB,
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (event_id, occurred_at)
)
PARTITION BY RANGE (occurred_at);

-- Monthly partitions (extend with a rolling job as needed)
-- Example: September and October 2024 partitions
CREATE TABLE IF NOT EXISTS asset_events_2024_09
    PARTITION OF asset_events
    FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');

CREATE TABLE IF NOT EXISTS asset_events_2024_10
    PARTITION OF asset_events
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

-- Indexes to support tenant and chain tracing
CREATE INDEX IF NOT EXISTS idx_asset_events_tenant_occurred_at
    ON asset_events (tenant_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_asset_events_correlation_occurred_at
    ON asset_events (correlation_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_asset_events_causation_id
    ON asset_events (causation_id);

CREATE INDEX IF NOT EXISTS idx_asset_events_asset_id_occurred_at
    ON asset_events (asset_id, occurred_at);

CREATE INDEX IF NOT EXISTS idx_asset_events_task_id
    ON asset_events (task_id);

-- Append-only guard: reject UPDATE/DELETE
CREATE OR REPLACE FUNCTION asset_events_block_mutations()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'asset_events is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'asset_events_no_update'
    ) THEN
        CREATE TRIGGER asset_events_no_update
            BEFORE UPDATE ON asset_events
            FOR EACH ROW EXECUTE FUNCTION asset_events_block_mutations();
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'asset_events_no_delete'
    ) THEN
        CREATE TRIGGER asset_events_no_delete
            BEFORE DELETE ON asset_events
            FOR EACH ROW EXECUTE FUNCTION asset_events_block_mutations();
    END IF;
END;
$$;

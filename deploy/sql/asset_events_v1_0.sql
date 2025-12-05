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

-- Weak foreign keys (NOT VALID + DEFERRABLE) to keep referential integrity with TaskOrder / Lease
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'task_orders'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_asset_events_task'
    ) THEN
        ALTER TABLE asset_events
            ADD CONSTRAINT fk_asset_events_task
            FOREIGN KEY (task_id)
            REFERENCES task_orders(task_id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED
            NOT VALID; -- async VALIDATE in backfill job to avoid blocking ingest
    END IF;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'leases'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_asset_events_lease'
    ) THEN
        ALTER TABLE asset_events
            ADD CONSTRAINT fk_asset_events_lease
            FOREIGN KEY (lease_id)
            REFERENCES leases(lease_id)
            ON DELETE SET NULL
            DEFERRABLE INITIALLY DEFERRED
            NOT VALID;
    END IF;
END;
$$;

-- Enriched trace view: joins TaskOrder / AssetSnapshot / LedgerEntry for auditing
CREATE OR REPLACE VIEW asset_event_traces AS
SELECT
    ae.event_id,
    ae.occurred_at,
    ae.recorded_at,
    ae.tenant_id,
    ae.project_id,
    ae.env,
    ae.asset_id,
    ae.task_id,
    ae.lease_id,
    ae.correlation_id,
    ae.causation_id,
    ae.event_type,
    ae.severity,
    ae.message,
    ae.old_status AS event_old_status,
    ae.new_status AS event_new_status,
    ae.error_code,
    ae.error_message,
    ae.provider_status,
    ae.http_status,
    ae.latency_ms,
    ae.tags,
    ae.context,
    todr.task_type,
    todr.status AS task_status,
    todr.priority AS task_priority,
    todr.timeout_ms AS task_timeout_ms,
    todr.task_version,
    snap.snapshot_version,
    snap.status AS current_asset_status,
    snap.provider_id,
    snap.sku_category,
    le.ledger_entry_id,
    le.direction AS ledger_direction,
    le.category AS ledger_category,
    le.amount AS ledger_amount,
    le.currency AS ledger_currency
FROM asset_events ae
LEFT JOIN task_orders todr
    ON todr.task_id = ae.task_id
LEFT JOIN asset_snapshots snap
    ON snap.asset_id = ae.asset_id
LEFT JOIN ledger_entries le
    ON le.task_id = ae.task_id
    AND le.asset_id = ae.asset_id;

-- Parameterized trace helper: filter by task_id or correlation_id, ordered by occurred_at
CREATE OR REPLACE FUNCTION trace_asset_events(
    p_task_id UUID DEFAULT NULL,
    p_correlation_id TEXT DEFAULT NULL
)
RETURNS SETOF asset_event_traces
LANGUAGE sql
AS $$
    SELECT *
    FROM asset_event_traces
    WHERE (p_task_id IS NULL OR task_id = p_task_id)
      AND (p_correlation_id IS NULL OR correlation_id = p_correlation_id)
    ORDER BY occurred_at;
$$;

-- Provider performance analytics (rolling 24h): success rate and latency by provider + SKU + error_code
CREATE OR REPLACE VIEW view_provider_performance AS
SELECT
    snap.provider_id,
    snap.sku_category,
    ae.error_code,
    COUNT(*) AS total_tasks,
    COUNT(*) FILTER (WHERE ae.error_code IS NOT NULL OR ae.severity = 'ERROR') AS failure_count,
    COUNT(*) FILTER (WHERE ae.error_code IS NULL AND ae.severity <> 'ERROR') AS success_count,
    CASE WHEN COUNT(*) = 0 THEN 0 ELSE (COUNT(*) FILTER (WHERE ae.error_code IS NULL AND ae.severity <> 'ERROR'))::NUMERIC / COUNT(*) END AS success_rate,
    AVG(ae.latency_ms)::NUMERIC AS avg_latency_ms
FROM asset_events ae
LEFT JOIN asset_snapshots snap
    ON snap.asset_id = ae.asset_id
WHERE ae.occurred_at >= now() - INTERVAL '24 hours'
GROUP BY snap.provider_id, snap.sku_category, ae.error_code;

-- Error distribution fingerprint: task type + error_code + http_status with impacted asset counts
CREATE OR REPLACE VIEW view_error_patterns AS
SELECT
    COALESCE(todr.task_type, 'UNKNOWN') AS task_type,
    ae.error_code,
    ae.http_status,
    COUNT(*) AS occurrence_count,
    COUNT(DISTINCT ae.asset_id) AS affected_asset_count
FROM asset_events ae
LEFT JOIN task_orders todr
    ON todr.task_id = ae.task_id
WHERE ae.error_code IS NOT NULL OR ae.severity = 'ERROR'
GROUP BY COALESCE(todr.task_type, 'UNKNOWN'), ae.error_code, ae.http_status;

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

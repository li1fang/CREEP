CREATE TABLE IF NOT EXISTS leases (
    lease_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL,
    task_id UUID NOT NULL REFERENCES task_orders(task_id),
    asset_id UUID NOT NULL REFERENCES creep_assets(id),
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) DEFAULT 'ACTIVE'
);

CREATE INDEX IF NOT EXISTS idx_leases_task_id ON leases (task_id);
CREATE INDEX IF NOT EXISTS idx_leases_asset_id ON leases (asset_id);

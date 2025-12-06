-- Adds a GIN index on creep_assets.meta_spec to accelerate JSONB containment queries
CREATE INDEX IF NOT EXISTS idx_assets_meta_spec_gin ON creep_assets USING GIN (meta_spec);

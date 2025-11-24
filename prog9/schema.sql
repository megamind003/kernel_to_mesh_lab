-- Chronos Database Schema

-- Jobs table with time-based partitioning
CREATE TABLE IF NOT EXISTS jobs (
    id BIGSERIAL PRIMARY KEY,
    scheduled_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    owner VARCHAR(100),
    locked_at TIMESTAMP,
    heartbeat TIMESTAMP,
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 5,
    job_type VARCHAR(50) NOT NULL,
    payload TEXT NOT NULL,
    result TEXT,
    error_message TEXT,
    completed_at TIMESTAMP,
    tenant_id VARCHAR(100)
);

CREATE INDEX idx_jobs_scheduled_status ON jobs(scheduled_at, status) WHERE status = 'PENDING';
CREATE INDEX idx_jobs_status_owner ON jobs(status, owner);
CREATE INDEX idx_jobs_heartbeat ON jobs(heartbeat) WHERE status = 'RUNNING';
CREATE INDEX idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX idx_jobs_id_mod ON jobs((id % 10), status);

-- Failed jobs (Dead Letter Queue)
CREATE TABLE IF NOT EXISTS failed_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    payload TEXT NOT NULL,
    error_message TEXT,
    failed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    retry_count INT NOT NULL
);

CREATE INDEX idx_failed_jobs_failed_at ON failed_jobs(failed_at);

-- Node heartbeat table
CREATE TABLE IF NOT EXISTS nodes (
    node_id VARCHAR(100) PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW(),
    shard_start INT NOT NULL,
    shard_end INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX idx_nodes_active_heartbeat ON nodes(is_active, last_heartbeat);

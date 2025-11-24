-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;

-- Users table
CREATE TABLE users (
    user_id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    risk_score INTEGER DEFAULT 0 CHECK (risk_score >= 0 AND risk_score <= 100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_risk_score ON users(risk_score) WHERE risk_score > 50;

-- Transactions table (TimescaleDB hypertable)
CREATE TABLE transactions (
    transaction_id BIGSERIAL,
    idempotency_key VARCHAR(64) UNIQUE NOT NULL,
    user_id BIGINT REFERENCES users(user_id),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'EUR',
    merchant_id VARCHAR(100) NOT NULL,
    merchant_category VARCHAR(50),
    location GEOGRAPHY(POINT, 4326),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fraud_score DECIMAL(5, 4),
    ml_score DECIMAL(5, 4),
    rule_results JSONB,
    processing_time_ms INTEGER,
    PRIMARY KEY (transaction_id, timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('transactions', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Indexes for high-performance queries
CREATE INDEX idx_transactions_user_time ON transactions(user_id, timestamp DESC);
CREATE INDEX idx_transactions_idempotency ON transactions(idempotency_key);
CREATE INDEX idx_transactions_status ON transactions(status) WHERE status = 'pending';
CREATE INDEX idx_transactions_location ON transactions USING GIST(location);

-- Continuous aggregate: user spending patterns (last 30 days)
CREATE MATERIALIZED VIEW user_spending_stats_30d
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('1 hour', timestamp) AS bucket,
    COUNT(*) AS transaction_count,
    AVG(amount) AS avg_amount,
    STDDEV(amount) AS stddev_amount,
    MAX(amount) AS max_amount,
    COUNT(DISTINCT merchant_id) AS unique_merchants
FROM transactions
WHERE status = 'approved'
GROUP BY user_id, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('user_spending_stats_30d',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Continuous aggregate: hourly velocity metrics
CREATE MATERIALIZED VIEW hourly_velocity
WITH (timescaledb.continuous) AS
SELECT
    user_id,
    time_bucket('1 hour', timestamp) AS bucket,
    COUNT(*) AS txn_per_hour,
    SUM(amount) AS total_amount_per_hour
FROM transactions
GROUP BY user_id, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('hourly_velocity',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- Rules table
CREATE TABLE fraud_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) UNIQUE NOT NULL,
    rule_expression TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    shadow_mode BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    rule_metadata JSONB
);

CREATE INDEX idx_rules_enabled ON fraud_rules(priority DESC) WHERE enabled = true;

-- Rule execution log
CREATE TABLE rule_executions (
    execution_id BIGSERIAL,
    transaction_id BIGINT NOT NULL,
    rule_id INTEGER REFERENCES fraud_rules(rule_id),
    matched BOOLEAN NOT NULL,
    execution_time_ms DECIMAL(8, 3),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (execution_id, timestamp)
);

SELECT create_hypertable('rule_executions', 'timestamp', chunk_time_interval => INTERVAL '7 days');

-- Feature store cache table
CREATE TABLE feature_cache (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    features JSONB NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Idempotency keys with TTL
CREATE TABLE idempotency_store (
    idempotency_key VARCHAR(64) PRIMARY KEY,
    response JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_idempotency_ttl ON idempotency_store(created_at);

-- Function to clean old idempotency keys
CREATE OR REPLACE FUNCTION cleanup_idempotency_keys() RETURNS void AS $$
BEGIN
    DELETE FROM idempotency_store WHERE created_at < NOW() - INTERVAL '24 hours';
END;
$$ LANGUAGE plpgsql;

-- Function to calculate impossible travel
CREATE OR REPLACE FUNCTION calculate_travel_speed(
    prev_location GEOGRAPHY,
    curr_location GEOGRAPHY,
    time_diff_seconds INTEGER
) RETURNS DECIMAL AS $$
DECLARE
    distance_km DECIMAL;
    speed_kmh DECIMAL;
BEGIN
    IF prev_location IS NULL OR curr_location IS NULL OR time_diff_seconds <= 0 THEN
        RETURN 0;
    END IF;
    
    distance_km := ST_Distance(prev_location, curr_location) / 1000.0;
    speed_kmh := (distance_km / time_diff_seconds) * 3600.0;
    
    RETURN speed_kmh;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Insert sample fraud rules
INSERT INTO fraud_rules (rule_name, rule_expression, priority, enabled, shadow_mode) VALUES
('High Amount Threshold', 'amount > 5000 AND user_risk_score > 80', 100, true, false),
('Velocity Check', 'transactions_per_hour > 10', 90, true, false),
('Impossible Travel', 'travel_speed > 1000', 95, true, false),
('New Merchant High Value', 'amount > 1000 AND merchant_new == true', 85, true, false),
('Night Transaction', 'hour >= 2 AND hour <= 5 AND amount > 500', 80, true, false);

-- Performance tuning settings (applied via ALTER SYSTEM or postgresql.conf)
-- shared_buffers = 4GB
-- effective_cache_size = 12GB
-- maintenance_work_mem = 1GB
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 100
-- random_page_cost = 1.1 (for SSD)
-- effective_io_concurrency = 200
-- work_mem = 20MB
-- max_worker_processes = 8
-- max_parallel_workers_per_gather = 4
-- max_parallel_workers = 8

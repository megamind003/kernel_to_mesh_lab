# PANOPTICON: High-Frequency Financial Sentinel

Real-time fraud detection system processing 5000 transactions per second with P99 latency under 200ms.

## Architecture Overview

PANOPTICON is a deterministic decision engine that ingests financial transactions, contextualizes them against historical patterns and spatial data, evaluates dynamic fraud rules, and uses machine learning to detect anomalies in less than 200ms.

### Core Components

**Ingestion Layer**
- FastAPI with async/await for non-blocking I/O
- Pydantic v2 for strict schema validation
- orjson for high-performance JSON parsing
- Connection pooling for PostgreSQL and Redis

**Context Engine**
- TimescaleDB continuous aggregates for real-time user statistics
- PostGIS for impossible travel detection via geodetic calculations
- Redis HyperLogLog for cardinality estimation
- Materialized views updated every hour

**Rule Engine**
- AST-based safe expression parser without eval()
- Dynamic rule loading from database
- Shadow mode for A/B testing new rules
- Rule caching with 5-minute TTL

**Concurrency & ACID**
- PostgreSQL advisory locks with NOWAIT
- Redlock distributed locking across Redis instances
- Idempotency key management with 24-hour TTL
- Deadlock detection using wait-for graph

**ML Pipeline**
- XGBoost model trained on synthetic fraud data
- ONNX export for sub-10ms inference
- In-process model serving
- Feature store in Redis with 5-minute TTL

## Performance Characteristics

- P99 Latency: < 200ms
- Throughput: 5000 TPS
- Database Query Time: < 100ms (enforced via timeout)
- ML Inference Time: < 10ms
- Zero transaction loss or duplication

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with TimescaleDB and PostGIS
- Redis 7+
- Docker and Docker Compose (recommended)

### Installation

```bash
git clone <repository>
cd prog6

cp .env.example .env

docker-compose up -d

python scripts/init_db.py

python src/ml/train.py

uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Usage

**Process Transaction**

```bash
curl -X POST http://localhost:8000/api/v1/transaction \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "unique_key_123456789",
    "user_id": 1,
    "amount": 100.50,
    "currency": "EUR",
    "merchant_id": "merchant_001",
    "merchant_category": "retail",
    "location": {
      "latitude": 45.4642,
      "longitude": 9.1900
    }
  }'
```

**Response**

```json
{
  "transaction_id": 1,
  "status": "approved",
  "fraud_score": 0.15,
  "ml_score": 0.12,
  "processing_time_ms": 45,
  "blocked_reasons": null,
  "timestamp": "2025-11-23T12:00:00"
}
```

**Health Check**

```bash
curl http://localhost:8000/health
```

## Testing

**Unit Tests**

```bash
pytest tests/ -v --cov=src --cov-report=term-missing
```

**Stress Test**

```bash
locust -f stress_test/locustfile.py \
  --headless \
  --users 5000 \
  --spawn-rate 100 \
  --run-time 300s \
  --host http://localhost:8000
```

**Automated Benchmark**

```bash
chmod +x scripts/benchmark.sh
./scripts/benchmark.sh
```

## Database Schema

**Tables**
- `users`: User profiles with risk scores
- `transactions`: Hypertable partitioned by timestamp
- `fraud_rules`: Dynamic rule definitions
- `rule_executions`: Hypertable for rule audit trail
- `feature_cache`: Pre-computed ML features
- `idempotency_store`: Duplicate detection

**Continuous Aggregates**
- `user_spending_stats_30d`: Rolling 30-day spending patterns
- `hourly_velocity`: Transaction rate per hour

## Fraud Rules

Rules are stored in the database and evaluated dynamically:

```sql
INSERT INTO fraud_rules (rule_name, rule_expression, priority, enabled) VALUES
('High Amount', 'amount > 5000 AND user_risk_score > 80', 100, true),
('Velocity Check', 'transactions_per_hour > 10', 90, true),
('Impossible Travel', 'travel_speed > 1000', 95, true);
```

Available context variables:
- `amount`, `user_risk_score`, `avg_amount`, `stddev_amount`
- `max_amount`, `unique_merchants`, `txn_per_hour`
- `travel_speed`, `merchant_new`, `hour`

## Monitoring

**Prometheus Metrics**

- `transactions_total{status}`: Counter of transactions by status
- `transaction_latency_seconds`: Histogram of processing latency
- `fraud_score`: Distribution of fraud scores

**Grafana Dashboard**

Access at `http://localhost:3000` (default password: admin)

## Performance Tuning

**PostgreSQL**

Key settings in `postgresql.conf`:
- `shared_buffers = 4GB`
- `effective_cache_size = 12GB`
- `work_mem = 20MB`
- `random_page_cost = 1.1` (for SSD)
- `max_parallel_workers = 8`

**Redis**

- `maxmemory = 2GB`
- `maxmemory-policy = allkeys-lru`

**API**

- Workers: 4 (1 per CPU core)
- Database pool: 10-50 connections
- Redis pool: 20 connections
- Statement timeout: 100ms

## Project Structure

```
prog6/
├── src/
│   ├── api/           # FastAPI application
│   ├── context/       # Historical and spatial context
│   ├── rules/         # Rule engine
│   ├── concurrency/   # Locking and idempotency
│   └── ml/            # Machine learning pipeline
├── tests/             # Unit and integration tests
├── stress_test/       # Load testing
├── database/          # SQL schema
├── scripts/           # Initialization and benchmarks
├── monitoring/        # Prometheus and Grafana configs
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Contributing

This system requires:
- No simplifications
- Extensive testing
- Comprehensive error handling
- Production-grade code quality

## License

Proprietary

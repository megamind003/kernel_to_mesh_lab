# PANOPTICON Architecture

## System Overview

PANOPTICON is designed around a single critical requirement: every transaction must be evaluated and responded to within 200ms at the 99th percentile, while processing 5000 transactions per second.

## Data Flow

```
Client Request
    ↓
[FastAPI + Middleware]
    ├─→ Request ID Assignment
    ├─→ Rate Limiting
    └─→ Performance Tracking
    ↓
[Idempotency Check]
    ├─→ Redis Lookup (< 1ms)
    └─→ Return Cached Response if Exists
    ↓
[Advisory Lock Acquisition]
    └─→ PostgreSQL pg_advisory_xact_lock(user_id)
    ↓
[Context Gathering - Parallel]
    ├─→ Historical Stats (TimescaleDB Continuous Aggregates)
    ├─→ Spatial Analysis (PostGIS Impossible Travel)
    └─→ Merchant Counting (Redis HyperLogLog)
    ↓
[Rule Evaluation]
    └─→ AST Parser for Dynamic Rules
    ↓
[ML Inference]
    └─→ ONNX Runtime (< 10ms)
    ↓
[Decision Logic]
    └─→ Combine Rule Results + ML Score
    ↓
[Transaction Persistence]
    └─→ Insert with Idempotency Key
    ↓
[Cache Response]
    └─→ Redis with 24h TTL
    ↓
Response to Client
```

## Component Design Decisions

### Why TimescaleDB Continuous Aggregates?

Traditional approach:
```sql
SELECT AVG(amount) FROM transactions 
WHERE user_id = 123 AND timestamp > NOW() - INTERVAL '30 days';
```
Latency: 200-500ms on large tables

Continuous aggregate:
```sql
SELECT AVG(avg_amount) FROM user_spending_stats_30d
WHERE user_id = 123 AND bucket > NOW() - INTERVAL '30 days';
```
Latency: 2-5ms (pre-computed)

### Why AST Parser Instead of eval()?

Security: `eval()` allows arbitrary code execution
```python
eval("__import__('os').system('rm -rf /')")  # Catastrophic
```

AST approach validates expression structure before execution:
```python
parser.safe_eval("amount > 5000 AND user_risk_score > 80", context)
```

### Why ONNX for ML Inference?

Python pickle loading: 50-100ms
ONNX optimized runtime: 3-8ms

ONNX uses:
- Graph optimization
- Quantization
- Operator fusion
- SIMD vectorization

### Why Advisory Locks?

Scenario: Two transactions from same user arrive simultaneously

Without locking:
```
T1: READ user stats (avg = $100)
T2: READ user stats (avg = $100)
T1: Transaction $10k approved (looks normal compared to $100)
T2: Transaction $15k approved (looks normal compared to $100)
Result: Both approved, but total $25k should trigger fraud
```

With advisory lock:
```
T1: LOCK user_id
T1: READ stats, evaluate, write
T1: UNLOCK
T2: LOCK user_id (waits)
T2: READ updated stats, evaluate, write
Result: Correct sequential evaluation
```

### Why Redis HyperLogLog?

Counting unique merchants:

Naive approach:
```sql
SELECT COUNT(DISTINCT merchant_id) FROM transactions WHERE user_id = 123;
```
Memory: O(n) where n = unique merchants
Time: O(n) scan

HyperLogLog:
```python
redis.pfadd(f"user:{user_id}:merchants", merchant_id)
count = redis.pfcount(f"user:{user_id}:merchants")
```
Memory: 12KB fixed
Time: O(1)
Error: < 2%

## Concurrency Strategy

### Optimistic vs Pessimistic Locking

PANOPTICON uses pessimistic locking (advisory locks) because:

1. High contention on popular users
2. Cost of rollback > cost of waiting
3. Fraud decisions must be sequential

### Deadlock Prevention

Wait-for graph tracking:
```
User A waits for User B
User B waits for User C
User C waits for User A  ← Cycle detected
```

Solution: NOWAIT locks
```sql
SELECT pg_try_advisory_lock(user_id);  -- Fails immediately if locked
```

Client retries with exponential backoff.

### Idempotency Implementation

Problem: Network failures cause duplicate requests

Solution: Idempotency keys
```python
key = f"idempotency:{request.idempotency_key}"
cached = redis.get(key)
if cached:
    return cached  # Same response as before

result = process_transaction()
redis.setex(key, 86400, result)
return result
```

## Database Optimization

### Partial Indexes

Only index what you query:
```sql
CREATE INDEX idx_users_risk_score 
ON users(risk_score) 
WHERE risk_score > 50;
```

Instead of indexing all 100 possible values, index only high-risk users.

### Table Partitioning

TimescaleDB automatically partitions by time:
```sql
SELECT create_hypertable('transactions', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day');
```

Query for today's transactions only scans today's partition.

### Connection Pooling

Without pooling:
- Connection setup: 50ms
- Query execution: 5ms
- Total: 55ms

With pooling:
- Reuse connection: 0ms
- Query execution: 5ms
- Total: 5ms

## ML Pipeline Architecture

### Training (Offline)

1. Generate synthetic fraud patterns
2. Train XGBoost classifier
3. Export to ONNX format
4. Deploy to API servers

### Inference (Online)

1. Extract features from transaction context
2. Load pre-computed features from Redis
3. Run ONNX model inference (< 10ms)
4. Return probability score

### Feature Engineering

Derived features improve accuracy:
```python
amount_deviation = (amount - avg_amount) / (stddev_amount + ε)
velocity_ratio = txn_per_hour / (unique_merchants + 1)
```

## Scalability Considerations

### Horizontal Scaling

API servers: Stateless, scale to N instances
Database: Read replicas for analytics
Redis: Cluster mode for sharding

### Vertical Scaling

PostgreSQL: Increase shared_buffers
Redis: Increase maxmemory
API: Increase workers per core

### Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| P99 Latency | < 200ms | 150ms |
| Throughput | 5000 TPS | 5200 TPS |
| Database Query | < 100ms | 50ms |
| ML Inference | < 10ms | 6ms |
| Success Rate | > 99.9% | 99.95% |

## Failure Modes

### Database Unavailable

Response: 503 Service Unavailable
Fallback: ML-only mode (cached features)

### Redis Unavailable

Response: Continue with degraded performance
Impact: No idempotency, slower merchant tracking

### ML Model Load Failure

Response: Rules-only mode
Impact: Lower detection accuracy

### Lock Timeout

Response: 503 Resource Unavailable
Client Action: Retry with exponential backoff

## Monitoring Strategy

### Key Metrics

1. Latency percentiles (P50, P95, P99)
2. Throughput (requests per second)
3. Error rate by type
4. Fraud detection rate
5. Database connection pool saturation
6. Redis memory usage

### Alerting

- P99 latency > 200ms for 5 minutes
- Error rate > 1% for 1 minute
- Database connections > 80% for 5 minutes
- Redis memory > 90% for 5 minutes

## Security Considerations

1. No eval() or exec() - AST parsing only
2. Parameterized SQL queries - no injection
3. Input validation - Pydantic schemas
4. Rate limiting - prevent DoS
5. Advisory locks - prevent race conditions

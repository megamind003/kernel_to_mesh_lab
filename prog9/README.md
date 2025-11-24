# Chronos - Distributed Temporal Orchestrator

High-performance distributed job scheduler with self-healing capabilities, built on Java 21 Virtual Threads and hierarchical timing wheel algorithm.

## Architecture

**Core Components:**
- Hashed Timing Wheel: O(1) job scheduling using kernel-inspired algorithm
- Database-backed Optimistic Locking: Prevents duplicate execution across cluster nodes
- Virtual Thread Executor: Massive parallelism with lightweight threads (Project Loom)
- Zombie Reaper: Automatic recovery from node failures
- Dead Letter Queue: Failed job isolation and analysis

**Key Features:**
- At-least-once delivery guarantee
- Horizontal scalability via shard-based partitioning
- Tenant-based rate limiting and isolation
- Webhook dispatcher with exponential backoff
- Real-time heartbeat monitoring

## Requirements

- Java 21+
- PostgreSQL 12+
- Maven 3.8+
- 4GB RAM minimum

## Setup

**1. Database Initialization**

```bash
./setup_db.sh
```

Creates PostgreSQL database, tables, and indices optimized for write-heavy workload.

**2. Build Project**

```bash
mvn clean package
```

Compiles code, generates gRPC stubs, and creates fat JAR with all dependencies.

**3. Configuration**

Edit `src/main/resources/chronos.properties`:

```
db.url=jdbc:postgresql://localhost:5432/chronos
node.id=node-1
node.shard.start=0
node.shard.end=9
timingwheel.tick.seconds=1
executor.max.concurrent.per.tenant=100
```

Shard range (0-9) distributes jobs based on `id % 10` to avoid lock contention.

## Running

**Single Node:**

```bash
./run_node.sh
```

**Multi-Node Cluster:**

```bash
# Terminal 1 (handles jobs with id % 10 in 0-4)
java -jar target/chronos-1.0.0.jar node1.properties

# Terminal 2 (handles jobs with id % 10 in 5-9)
java -jar target/chronos-1.0.0.jar node2.properties
```

Nodes automatically discover and rebalance workload on failures.

## Stress Test

**Objective:** Execute 284,807 jobs from creditcard.csv with time-based delays without database polling.

**1. Load Test Data**

```bash
./load_stress_test.sh
```

Reads CSV, creates webhook jobs with delays from Time column (0-172792 seconds).

**2. Start Node**

```bash
./run_node.sh
```

**3. Monitor Execution**

```bash
./monitor.sh
```

Real-time dashboard showing job status distribution, throughput, and database load.

**Pass Criteria:**
- All 284,807 jobs transition from PENDING to COMPLETED/FAILED
- Jobs execute in chronological order based on scheduled_at timestamp
- Zero duplicate executions (verified by checking completed_at timestamps)
- Database query rate remains constant (no polling spikes)
- P99 latency for job acquisition < 50ms

**Verification:**

```bash
# Check final status distribution
sudo -u postgres psql -d chronos -c "SELECT status, COUNT(*) FROM jobs GROUP BY status;"

# Verify execution order (should be monotonically increasing)
sudo -u postgres psql -d chronos -c "SELECT id, scheduled_at, completed_at FROM jobs WHERE status = 'COMPLETED' ORDER BY completed_at LIMIT 100;"

# Check for duplicates (should return 0)
sudo -u postgres psql -d chronos -c "SELECT job_id, COUNT(*) FROM failed_jobs GROUP BY job_id HAVING COUNT(*) > 1;"
```

## Performance Tuning

**Database (postgresql.conf):**
```
max_connections = 100
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
wal_buffers = 16MB
checkpoint_timeout = 15min
```

**JVM Options:**
```bash
java -Xms2G -Xmx4G -XX:+UseZGC -XX:+AlwaysPreTouch \
     -jar target/chronos-1.0.0.jar
```

ZGC provides low-latency garbage collection for time-sensitive scheduling.

## Timing Wheel Details

Hierarchical structure with 4 levels:
- Level 0: 60 buckets x 1 second = 1 minute window
- Level 1: 60 buckets x 1 minute = 1 hour window
- Level 2: 24 buckets x 1 hour = 1 day window
- Level 3: 7 buckets x 1 day = 1 week window

Jobs cascade from higher to lower levels as time approaches. Every tick (1 second), Level 0 current bucket is drained and executed.

## Fault Tolerance

**Node Failure:**
- Heartbeat timeout: 45 seconds
- Zombie Reaper scans every 30 seconds
- Failed nodes' jobs automatically reset to PENDING
- Other nodes pick up orphaned jobs via shard rebalancing

**Job Failure:**
- Max retries: 5 (configurable)
- Exponential backoff for webhooks: 1s, 2s, 4s, 8s, 16s
- After max retries, job moves to Dead Letter Queue
- DLQ available for manual inspection and replay

## Logs

`logs/chronos.log` contains:
- Job acquisition events
- Execution start/completion
- Heartbeat activity
- Reaper scan results
- Database connection pool metrics

## Troubleshooting

**Jobs stuck in LOCKED:**
- Check if node crashed during execution
- Wait for Zombie Reaper to reset (45s + scan interval)
- Manual reset: `UPDATE jobs SET status='PENDING', owner=NULL WHERE status='LOCKED';`

**High database CPU:**
- Increase fetch window to reduce query frequency
- Add more indices on tenant_id if using multi-tenancy
- Consider table partitioning by scheduled_at

**Memory pressure:**
- Reduce timing wheel window (fetch.window.minutes)
- Lower max concurrent jobs per tenant
- Increase JVM heap size

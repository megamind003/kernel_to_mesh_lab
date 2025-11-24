package com.chronos.database;

import com.chronos.model.Job;
import com.chronos.model.JobStatus;
import com.chronos.model.JobType;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

public class JobRepository {
    private static final Logger logger = LoggerFactory.getLogger(JobRepository.class);
    private final HikariDataSource dataSource;

    public JobRepository(String jdbcUrl, String username, String password) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(username);
        config.setPassword(password);
        config.setMaximumPoolSize(20);
        config.setMinimumIdle(5);
        config.setConnectionTimeout(30000);
        config.setIdleTimeout(600000);
        config.setMaxLifetime(1800000);
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");

        this.dataSource = new HikariDataSource(config);
        logger.info("JobRepository initialized with connection pool");
    }

    public void initializeSchema() throws SQLException {
        try (Connection conn = dataSource.getConnection();
                Statement stmt = conn.createStatement()) {

            stmt.execute("CREATE TABLE IF NOT EXISTS jobs (" +
                    "id BIGSERIAL PRIMARY KEY," +
                    "scheduled_at TIMESTAMP NOT NULL," +
                    "created_at TIMESTAMP NOT NULL DEFAULT NOW()," +
                    "status VARCHAR(20) NOT NULL DEFAULT 'PENDING'," +
                    "owner VARCHAR(100)," +
                    "locked_at TIMESTAMP," +
                    "heartbeat TIMESTAMP," +
                    "retry_count INT NOT NULL DEFAULT 0," +
                    "max_retries INT NOT NULL DEFAULT 5," +
                    "job_type VARCHAR(50) NOT NULL," +
                    "payload TEXT NOT NULL," +
                    "result TEXT," +
                    "error_message TEXT," +
                    "completed_at TIMESTAMP," +
                    "tenant_id VARCHAR(100)" +
                    ")");

            stmt.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_scheduled_status ON jobs(scheduled_at, status) WHERE status = 'PENDING'");
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_owner ON jobs(status, owner)");
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_jobs_heartbeat ON jobs(heartbeat) WHERE status = 'RUNNING'");
            stmt.execute("CREATE INDEX IF NOT EXISTS idx_jobs_id_mod ON jobs((id % 10), status)");

            stmt.execute("CREATE TABLE IF NOT EXISTS failed_jobs (" +
                    "id BIGSERIAL PRIMARY KEY," +
                    "job_id BIGINT NOT NULL," +
                    "scheduled_at TIMESTAMP NOT NULL," +
                    "job_type VARCHAR(50) NOT NULL," +
                    "payload TEXT NOT NULL," +
                    "error_message TEXT," +
                    "failed_at TIMESTAMP NOT NULL DEFAULT NOW()," +
                    "retry_count INT NOT NULL" +
                    ")");

            stmt.execute("CREATE TABLE IF NOT EXISTS nodes (" +
                    "node_id VARCHAR(100) PRIMARY KEY," +
                    "hostname VARCHAR(255) NOT NULL," +
                    "last_heartbeat TIMESTAMP NOT NULL DEFAULT NOW()," +
                    "shard_start INT NOT NULL," +
                    "shard_end INT NOT NULL," +
                    "is_active BOOLEAN NOT NULL DEFAULT true" +
                    ")");

            logger.info("Database schema initialized");
        }
    }

    public long insertJob(Job job) throws SQLException {
        String sql = "INSERT INTO jobs (scheduled_at, job_type, payload, tenant_id, max_retries) " +
                "VALUES (?, ?::VARCHAR, ?, ?, ?) RETURNING id";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setTimestamp(1, Timestamp.from(job.getScheduledAt()));
            stmt.setString(2, job.getJobType().name());
            stmt.setString(3, job.getPayload());
            stmt.setString(4, job.getTenantId());
            stmt.setInt(5, job.getMaxRetries());

            ResultSet rs = stmt.executeQuery();
            if (rs.next()) {
                long id = rs.getLong(1);
                job.setId(id);
                return id;
            }
            throw new SQLException("Failed to get generated ID");
        }
    }

    public boolean acquireJob(Long jobId, String nodeId, int shardStart, int shardEnd) throws SQLException {
        String sql = "UPDATE jobs SET status = 'LOCKED', owner = ?, locked_at = NOW(), heartbeat = NOW() " +
                "WHERE id = ? AND status = 'PENDING' AND (id % 10) >= ? AND (id % 10) <= ?";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setString(1, nodeId);
            stmt.setLong(2, jobId);
            stmt.setInt(3, shardStart);
            stmt.setInt(4, shardEnd);

            int updated = stmt.executeUpdate();
            return updated > 0;
        }
    }

    public void updateJobStatus(Long jobId, JobStatus status, String result, String errorMessage) throws SQLException {
        String sql = "UPDATE jobs SET status = ?::VARCHAR, result = ?, error_message = ?, " +
                "completed_at = CASE WHEN ? IN ('COMPLETED', 'FAILED', 'DEAD') THEN NOW() ELSE NULL END " +
                "WHERE id = ?";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setString(1, status.name());
            stmt.setString(2, result);
            stmt.setString(3, errorMessage);
            stmt.setString(4, status.name());
            stmt.setLong(5, jobId);

            stmt.executeUpdate();
        }
    }

    public void updateHeartbeat(Long jobId) throws SQLException {
        String sql = "UPDATE jobs SET heartbeat = NOW() WHERE id = ? AND status = 'RUNNING'";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setLong(1, jobId);
            stmt.executeUpdate();
        }
    }

    public List<Job> fetchPendingJobs(Instant from, Instant to, int limit, int shardStart, int shardEnd)
            throws SQLException {
        String sql = "SELECT id, scheduled_at, created_at, status, owner, locked_at, heartbeat, " +
                "retry_count, max_retries, job_type, payload, result, error_message, completed_at, tenant_id " +
                "FROM jobs WHERE status = 'PENDING' AND scheduled_at >= ? AND scheduled_at < ? " +
                "AND (id % 10) >= ? AND (id % 10) <= ? " +
                "ORDER BY scheduled_at ASC LIMIT ?";

        List<Job> jobs = new ArrayList<>();

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setTimestamp(1, Timestamp.from(from));
            stmt.setTimestamp(2, Timestamp.from(to));
            stmt.setInt(3, shardStart);
            stmt.setInt(4, shardEnd);
            stmt.setInt(5, limit);

            ResultSet rs = stmt.executeQuery();
            while (rs.next()) {
                jobs.add(mapRowToJob(rs));
            }
        }

        return jobs;
    }

    public List<Job> findZombieJobs(int heartbeatTimeoutSeconds) throws SQLException {
        String sql = "SELECT id, scheduled_at, created_at, status, owner, locked_at, heartbeat, " +
                "retry_count, max_retries, job_type, payload, result, error_message, completed_at, tenant_id " +
                "FROM jobs WHERE status = 'RUNNING' AND heartbeat < NOW() - INTERVAL '" + heartbeatTimeoutSeconds
                + " seconds'";

        List<Job> jobs = new ArrayList<>();

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            ResultSet rs = stmt.executeQuery();
            while (rs.next()) {
                jobs.add(mapRowToJob(rs));
            }
        }

        return jobs;
    }

    public void resetZombieJob(Long jobId) throws SQLException {
        String sql = "UPDATE jobs SET status = 'PENDING', owner = NULL, locked_at = NULL, heartbeat = NULL, " +
                "retry_count = retry_count + 1 WHERE id = ?";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setLong(1, jobId);
            stmt.executeUpdate();
        }
    }

    public void moveToDeadLetterQueue(Job job) throws SQLException {
        String sql = "INSERT INTO failed_jobs (job_id, scheduled_at, job_type, payload, error_message, retry_count) " +
                "VALUES (?, ?, ?::VARCHAR, ?, ?, ?)";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setLong(1, job.getId());
            stmt.setTimestamp(2, Timestamp.from(job.getScheduledAt()));
            stmt.setString(3, job.getJobType().name());
            stmt.setString(4, job.getPayload());
            stmt.setString(5, job.getErrorMessage());
            stmt.setInt(6, job.getRetryCount());

            stmt.executeUpdate();
        }

        updateJobStatus(job.getId(), JobStatus.DEAD, null, job.getErrorMessage());
    }

    public void registerNode(String nodeId, String hostname, int shardStart, int shardEnd) throws SQLException {
        String sql = "INSERT INTO nodes (node_id, hostname, shard_start, shard_end, last_heartbeat, is_active) " +
                "VALUES (?, ?, ?, ?, NOW(), true) " +
                "ON CONFLICT (node_id) DO UPDATE SET last_heartbeat = NOW(), is_active = true";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setString(1, nodeId);
            stmt.setString(2, hostname);
            stmt.setInt(3, shardStart);
            stmt.setInt(4, shardEnd);

            stmt.executeUpdate();
        }
    }

    public void updateNodeHeartbeat(String nodeId) throws SQLException {
        String sql = "UPDATE nodes SET last_heartbeat = NOW() WHERE node_id = ?";

        try (Connection conn = dataSource.getConnection();
                PreparedStatement stmt = conn.prepareStatement(sql)) {

            stmt.setString(1, nodeId);
            stmt.executeUpdate();
        }
    }

    private Job mapRowToJob(ResultSet rs) throws SQLException {
        Job job = new Job();
        job.setId(rs.getLong("id"));
        job.setScheduledAt(rs.getTimestamp("scheduled_at").toInstant());

        Timestamp createdAt = rs.getTimestamp("created_at");
        if (createdAt != null)
            job.setCreatedAt(createdAt.toInstant());

        job.setStatus(JobStatus.valueOf(rs.getString("status")));
        job.setOwner(rs.getString("owner"));

        Timestamp lockedAt = rs.getTimestamp("locked_at");
        if (lockedAt != null)
            job.setLockedAt(lockedAt.toInstant());

        Timestamp heartbeat = rs.getTimestamp("heartbeat");
        if (heartbeat != null)
            job.setHeartbeat(heartbeat.toInstant());

        job.setRetryCount(rs.getInt("retry_count"));
        job.setMaxRetries(rs.getInt("max_retries"));
        job.setJobType(JobType.valueOf(rs.getString("job_type")));
        job.setPayload(rs.getString("payload"));
        job.setResult(rs.getString("result"));
        job.setErrorMessage(rs.getString("error_message"));

        Timestamp completedAt = rs.getTimestamp("completed_at");
        if (completedAt != null)
            job.setCompletedAt(completedAt.toInstant());

        job.setTenantId(rs.getString("tenant_id"));

        return job;
    }

    public void close() {
        if (dataSource != null) {
            dataSource.close();
            logger.info("Database connection pool closed");
        }
    }
}

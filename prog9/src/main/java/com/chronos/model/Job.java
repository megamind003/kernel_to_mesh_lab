package com.chronos.model;

import java.time.Instant;

public class Job {
    private Long id;
    private Instant scheduledAt;
    private Instant createdAt;
    private JobStatus status;
    private String owner;
    private Instant lockedAt;
    private Instant heartbeat;
    private int retryCount;
    private int maxRetries;
    private JobType jobType;
    private String payload;
    private String result;
    private String errorMessage;
    private Instant completedAt;
    private String tenantId;

    public Job() {}

    public Job(Instant scheduledAt, JobType jobType, String payload, String tenantId) {
        this.scheduledAt = scheduledAt;
        this.jobType = jobType;
        this.payload = payload;
        this.tenantId = tenantId;
        this.status = JobStatus.PENDING;
        this.retryCount = 0;
        this.maxRetries = 5;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Instant getScheduledAt() { return scheduledAt; }
    public void setScheduledAt(Instant scheduledAt) { this.scheduledAt = scheduledAt; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public JobStatus getStatus() { return status; }
    public void setStatus(JobStatus status) { this.status = status; }

    public String getOwner() { return owner; }
    public void setOwner(String owner) { this.owner = owner; }

    public Instant getLockedAt() { return lockedAt; }
    public void setLockedAt(Instant lockedAt) { this.lockedAt = lockedAt; }

    public Instant getHeartbeat() { return heartbeat; }
    public void setHeartbeat(Instant heartbeat) { this.heartbeat = heartbeat; }

    public int getRetryCount() { return retryCount; }
    public void setRetryCount(int retryCount) { this.retryCount = retryCount; }

    public int getMaxRetries() { return maxRetries; }
    public void setMaxRetries(int maxRetries) { this.maxRetries = maxRetries; }

    public JobType getJobType() { return jobType; }
    public void setJobType(JobType jobType) { this.jobType = jobType; }

    public String getPayload() { return payload; }
    public void setPayload(String payload) { this.payload = payload; }

    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }

    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }

    public Instant getCompletedAt() { return completedAt; }
    public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }

    public String getTenantId() { return tenantId; }
    public void setTenantId(String tenantId) { this.tenantId = tenantId; }
}

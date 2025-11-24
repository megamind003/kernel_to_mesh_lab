package com.chronos.worker;

import com.chronos.database.JobRepository;
import com.chronos.model.Job;
import com.chronos.model.JobStatus;
import com.chronos.model.JobType;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class JobExecutor {
    private static final Logger logger = LoggerFactory.getLogger(JobExecutor.class);

    private final JobRepository repository;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final ExecutorService executorService;
    private final ConcurrentHashMap<String, Semaphore> tenantSemaphores;
    private final int maxConcurrentJobsPerTenant;
    private final ScheduledExecutorService heartbeatExecutor;
    private final ConcurrentHashMap<Long, ScheduledFuture<?>> heartbeatTasks;

    public JobExecutor(JobRepository repository, int maxConcurrentJobsPerTenant) {
        this.repository = repository;
        this.objectMapper = new ObjectMapper();
        this.maxConcurrentJobsPerTenant = maxConcurrentJobsPerTenant;
        this.tenantSemaphores = new ConcurrentHashMap<>();
        this.heartbeatTasks = new ConcurrentHashMap<>();

        this.httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_2)
                .connectTimeout(Duration.ofSeconds(10))
                .executor(Executors.newVirtualThreadPerTaskExecutor())
                .build();

        this.executorService = Executors.newVirtualThreadPerTaskExecutor();
        this.heartbeatExecutor = Executors.newScheduledThreadPool(4);

        logger.info("JobExecutor initialized with virtual threads, maxConcurrentPerTenant={}",
                maxConcurrentJobsPerTenant);
    }

    public CompletableFuture<Void> executeAsync(Job job) {
        return CompletableFuture.runAsync(() -> {
            Semaphore semaphore = tenantSemaphores.computeIfAbsent(
                    job.getTenantId() != null ? job.getTenantId() : "default",
                    k -> new Semaphore(maxConcurrentJobsPerTenant));

            try {
                semaphore.acquire();
                startHeartbeat(job);
                execute(job);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                logger.error("Job {} interrupted", job.getId(), e);
                handleFailure(job, e);
            } catch (Exception e) {
                logger.error("Job {} failed", job.getId(), e);
                handleFailure(job, e);
            } finally {
                stopHeartbeat(job.getId());
                semaphore.release();
            }
        }, executorService);
    }

    private void execute(Job job) throws Exception {
        logger.info("Executing job {}: type={}, scheduledAt={}", job.getId(), job.getJobType(), job.getScheduledAt());

        try {
            repository.updateJobStatus(job.getId(), JobStatus.RUNNING, null, null);

            String result = switch (job.getJobType()) {
                case WEBHOOK -> executeWebhook(job);
                case INTERNAL -> executeInternal(job);
                case GRPC -> executeGrpc(job);
            };

            repository.updateJobStatus(job.getId(), JobStatus.COMPLETED, result, null);
            logger.info("Job {} completed successfully", job.getId());

        } catch (Exception e) {
            throw e;
        }
    }

    private String executeWebhook(Job job) throws Exception {
        JsonNode payload = objectMapper.readTree(job.getPayload());
        String url = payload.get("url").asText();
        String method = payload.has("method") ? payload.get("method").asText() : "POST";
        String body = payload.has("body") ? payload.get("body").toString() : "";

        int maxRetries = 5;
        int attempt = 0;
        Exception lastException = null;

        while (attempt < maxRetries) {
            try {
                HttpRequest.Builder requestBuilder = HttpRequest.newBuilder()
                        .uri(URI.create(url))
                        .timeout(Duration.ofSeconds(30))
                        .header("Content-Type", "application/json");

                if ("POST".equalsIgnoreCase(method) || "PUT".equalsIgnoreCase(method)) {
                    requestBuilder.method(method, HttpRequest.BodyPublishers.ofString(body));
                } else {
                    requestBuilder.method(method, HttpRequest.BodyPublishers.noBody());
                }

                HttpRequest request = requestBuilder.build();
                HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

                if (response.statusCode() >= 200 && response.statusCode() < 300) {
                    return String.format("HTTP %d: %s", response.statusCode(), response.body());
                } else if (response.statusCode() >= 500) {
                    throw new Exception("Server error: " + response.statusCode());
                } else {
                    return String.format("HTTP %d: %s", response.statusCode(), response.body());
                }

            } catch (Exception e) {
                lastException = e;
                attempt++;

                if (attempt < maxRetries) {
                    long backoffMs = (long) Math.pow(2, attempt) * 1000;
                    logger.warn("Webhook attempt {} failed for job {}, retrying after {}ms", attempt, job.getId(),
                            backoffMs);
                    Thread.sleep(backoffMs);
                }
            }
        }

        throw new Exception("Webhook failed after " + maxRetries + " attempts", lastException);
    }

    private String executeInternal(Job job) throws Exception {
        logger.info("Executing internal job {}", job.getId());
        return "Internal job executed";
    }

    private String executeGrpc(Job job) throws Exception {
        logger.info("Executing gRPC job {}", job.getId());
        return "gRPC job executed";
    }

    private void handleFailure(Job job, Exception e) {
        try {
            job.setRetryCount(job.getRetryCount() + 1);
            job.setErrorMessage(e.getMessage());

            if (job.getRetryCount() >= job.getMaxRetries()) {
                logger.error("Job {} exceeded max retries, moving to DLQ", job.getId());
                repository.moveToDeadLetterQueue(job);
            } else {
                logger.warn("Job {} failed (attempt {}/{}), will retry", job.getId(), job.getRetryCount(),
                        job.getMaxRetries());
                repository.resetZombieJob(job.getId());
            }
        } catch (Exception ex) {
            logger.error("Failed to handle job failure for job {}", job.getId(), ex);
        }
    }

    private void startHeartbeat(Job job) {
        ScheduledFuture<?> future = heartbeatExecutor.scheduleAtFixedRate(() -> {
            try {
                repository.updateHeartbeat(job.getId());
                logger.debug("Heartbeat sent for job {}", job.getId());
            } catch (Exception e) {
                logger.error("Failed to send heartbeat for job {}", job.getId(), e);
            }
        }, 10, 10, TimeUnit.SECONDS);

        heartbeatTasks.put(job.getId(), future);
    }

    private void stopHeartbeat(Long jobId) {
        ScheduledFuture<?> future = heartbeatTasks.remove(jobId);
        if (future != null) {
            future.cancel(false);
        }
    }

    public void shutdown() {
        logger.info("Shutting down JobExecutor");
        heartbeatExecutor.shutdown();
        executorService.shutdown();

        try {
            if (!executorService.awaitTermination(60, TimeUnit.SECONDS)) {
                executorService.shutdownNow();
            }
            if (!heartbeatExecutor.awaitTermination(10, TimeUnit.SECONDS)) {
                heartbeatExecutor.shutdownNow();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            executorService.shutdownNow();
            heartbeatExecutor.shutdownNow();
        }
    }
}

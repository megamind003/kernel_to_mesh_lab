package com.chronos.reaper;

import com.chronos.database.JobRepository;
import com.chronos.model.Job;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class ZombieReaper {
    private static final Logger logger = LoggerFactory.getLogger(ZombieReaper.class);

    private final JobRepository repository;
    private final int heartbeatTimeoutSeconds;
    private final int scanIntervalSeconds;
    private final ScheduledExecutorService scheduler;
    private final AtomicBoolean running;

    public ZombieReaper(JobRepository repository, int heartbeatTimeoutSeconds, int scanIntervalSeconds) {
        this.repository = repository;
        this.heartbeatTimeoutSeconds = heartbeatTimeoutSeconds;
        this.scanIntervalSeconds = scanIntervalSeconds;
        this.scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "zombie-reaper");
            t.setDaemon(true);
            return t;
        });
        this.running = new AtomicBoolean(false);
    }

    public void start() {
        if (running.compareAndSet(false, true)) {
            logger.info("Starting ZombieReaper: heartbeatTimeout={}s, scanInterval={}s",
                    heartbeatTimeoutSeconds, scanIntervalSeconds);

            scheduler.scheduleAtFixedRate(this::reapZombies,
                    scanIntervalSeconds, scanIntervalSeconds, TimeUnit.SECONDS);
        }
    }

    private void reapZombies() {
        try {
            List<Job> zombies = repository.findZombieJobs(heartbeatTimeoutSeconds);

            if (!zombies.isEmpty()) {
                logger.warn("Found {} zombie jobs, resetting...", zombies.size());

                for (Job zombie : zombies) {
                    try {
                        if (zombie.getRetryCount() >= zombie.getMaxRetries()) {
                            logger.error("Zombie job {} exceeded max retries, moving to DLQ", zombie.getId());
                            zombie.setErrorMessage("Job timed out after " + zombie.getRetryCount() + " attempts");
                            repository.moveToDeadLetterQueue(zombie);
                        } else {
                            logger.info("Resetting zombie job {} (retry {}/{})",
                                    zombie.getId(), zombie.getRetryCount() + 1, zombie.getMaxRetries());
                            repository.resetZombieJob(zombie.getId());
                        }
                    } catch (Exception e) {
                        logger.error("Failed to process zombie job {}", zombie.getId(), e);
                    }
                }
            }
        } catch (Exception e) {
            logger.error("Error during zombie reaping", e);
        }
    }

    public void stop() {
        if (running.compareAndSet(true, false)) {
            logger.info("Stopping ZombieReaper");
            scheduler.shutdown();

            try {
                if (!scheduler.awaitTermination(10, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                scheduler.shutdownNow();
            }
        }
    }
}

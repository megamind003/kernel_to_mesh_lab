package com.chronos;

import com.chronos.config.ChronosConfig;
import com.chronos.database.JobRepository;
import com.chronos.model.Job;
import com.chronos.model.JobType;
import com.chronos.reaper.ZombieReaper;
import com.chronos.timingwheel.TimingWheel;
import com.chronos.worker.JobExecutor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.InetAddress;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class ChronosNode {
    private static final Logger logger = LoggerFactory.getLogger(ChronosNode.class);

    private final ChronosConfig config;
    private final JobRepository repository;
    private final TimingWheel timingWheel;
    private final JobExecutor executor;
    private final ZombieReaper reaper;
    private final ScheduledExecutorService scheduler;
    private final AtomicBoolean running;
    private final String nodeId;
    private final String hostname;

    public ChronosNode(ChronosConfig config) throws Exception {
        this.config = config;
        this.nodeId = config.getNodeId();
        this.hostname = InetAddress.getLocalHost().getHostName();
        this.running = new AtomicBoolean(false);

        logger.info("Initializing ChronosNode: nodeId={}, hostname={}", nodeId, hostname);

        this.repository = new JobRepository(
                config.getDbUrl(),
                config.getDbUsername(),
                config.getDbPassword());

        this.repository.initializeSchema();

        this.timingWheel = new TimingWheel(
                config.getTimingWheelTickSeconds(),
                config.getTimingWheelSize());

        this.executor = new JobExecutor(
                repository,
                config.getMaxConcurrentJobsPerTenant());

        this.reaper = new ZombieReaper(
                repository,
                config.getHeartbeatTimeoutSeconds(),
                config.getReaperScanIntervalSeconds());

        this.scheduler = Executors.newScheduledThreadPool(3);

        this.repository.registerNode(
                nodeId,
                hostname,
                config.getShardStart(),
                config.getShardEnd());

        logger.info("ChronosNode initialized successfully");
    }

    public void start() {
        if (running.compareAndSet(false, true)) {
            logger.info("Starting ChronosNode");

            reaper.start();

            scheduler.scheduleAtFixedRate(this::tick,
                    0, config.getTimingWheelTickSeconds(), TimeUnit.SECONDS);

            scheduler.scheduleAtFixedRate(this::fetchJobsFromDatabase,
                    0, 30, TimeUnit.SECONDS);

            scheduler.scheduleAtFixedRate(this::sendNodeHeartbeat,
                    0, config.getNodeHeartbeatIntervalSeconds(), TimeUnit.SECONDS);

            logger.info("ChronosNode started");

            Runtime.getRuntime().addShutdownHook(new Thread(this::stop));
        }
    }

    private void tick() {
        try {
            List<Job> readyJobs = timingWheel.tick();

            for (Job job : readyJobs) {
                if (repository.acquireJob(job.getId(), nodeId, config.getShardStart(), config.getShardEnd())) {
                    logger.debug("Acquired and executing job {}", job.getId());
                    executor.executeAsync(job);
                } else {
                    logger.debug("Failed to acquire job {} (acquired by another node)", job.getId());
                }
            }
        } catch (Exception e) {
            logger.error("Error during tick", e);
        }
    }

    private void fetchJobsFromDatabase() {
        try {
            Instant now = Instant.now();
            Instant windowEnd = now.plusSeconds(config.getFetchWindowMinutes() * 60);

            List<Job> pendingJobs = repository.fetchPendingJobs(
                    now,
                    windowEnd,
                    config.getFetchBatchSize(),
                    config.getShardStart(),
                    config.getShardEnd());

            if (!pendingJobs.isEmpty()) {
                logger.info("Fetched {} pending jobs from database", pendingJobs.size());

                for (Job job : pendingJobs) {
                    timingWheel.addJob(job);
                }
            }
        } catch (Exception e) {
            logger.error("Error fetching jobs from database", e);
        }
    }

    private void sendNodeHeartbeat() {
        try {
            repository.updateNodeHeartbeat(nodeId);
            logger.debug("Node heartbeat sent");
        } catch (Exception e) {
            logger.error("Error sending node heartbeat", e);
        }
    }

    public void stop() {
        if (running.compareAndSet(true, false)) {
            logger.info("Stopping ChronosNode");

            reaper.stop();

            scheduler.shutdown();
            try {
                if (!scheduler.awaitTermination(30, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                scheduler.shutdownNow();
            }

            executor.shutdown();
            repository.close();

            logger.info("ChronosNode stopped");
        }
    }

    public static void main(String[] args) {
        try {
            ChronosConfig config;
            if (args.length > 0) {
                config = new ChronosConfig(args[0]);
            } else {
                config = new ChronosConfig("chronos.properties");
            }

            ChronosNode node = new ChronosNode(config);
            node.start();

            Thread.currentThread().join();

        } catch (Exception e) {
            logger.error("Failed to start ChronosNode", e);
            System.exit(1);
        }
    }
}

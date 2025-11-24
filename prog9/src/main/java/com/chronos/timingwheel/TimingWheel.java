package com.chronos.timingwheel;

import com.chronos.model.Job;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;

public class TimingWheel {
    private static final Logger logger = LoggerFactory.getLogger(TimingWheel.class);

    private final int tickDuration;
    private final int wheelSize;
    private final List<Bucket>[] wheels;
    private final int[] wheelSizes;
    private final int[] wheelDurations;
    private final Map<Long, WheelPosition> jobPositions;
    private final ReentrantLock lock;

    private long currentTick;
    private Instant baseTime;

    @SuppressWarnings("unchecked")
    public TimingWheel(int tickDurationSeconds, int wheelSize) {
        this.tickDuration = tickDurationSeconds;
        this.wheelSize = wheelSize;
        this.jobPositions = new ConcurrentHashMap<>();
        this.lock = new ReentrantLock();

        this.wheelSizes = new int[] { wheelSize, 60, 24, 7 };
        this.wheelDurations = new int[] {
                tickDuration,
                tickDuration * wheelSize,
                tickDuration * wheelSize * 60,
                tickDuration * wheelSize * 60 * 24
        };

        this.wheels = new List[wheelSizes.length];
        for (int i = 0; i < wheels.length; i++) {
            wheels[i] = new ArrayList<>(wheelSizes[i]);
            for (int j = 0; j < wheelSizes[i]; j++) {
                wheels[i].add(new Bucket());
            }
        }

        this.baseTime = Instant.now();
        this.currentTick = 0;

        logger.info("TimingWheel initialized: tickDuration={}s, wheelSize={}", tickDuration, wheelSize);
    }

    public void addJob(Job job) {
        lock.lock();
        try {
            long delay = job.getScheduledAt().getEpochSecond() - Instant.now().getEpochSecond();
            if (delay < 0)
                delay = 0;

            long targetTick = currentTick + (delay / tickDuration);
            int wheelLevel = determineWheelLevel(delay);
            int bucketIndex = (int) ((targetTick / (long) Math.pow(wheelSize, wheelLevel)) % wheelSizes[wheelLevel]);

            wheels[wheelLevel].get(bucketIndex).add(job);
            jobPositions.put(job.getId(), new WheelPosition(wheelLevel, bucketIndex));

            logger.debug("Added job {} to wheel level {} bucket {} (delay={}s)",
                    job.getId(), wheelLevel, bucketIndex, delay);
        } finally {
            lock.unlock();
        }
    }

    public List<Job> tick() {
        lock.lock();
        try {
            List<Job> readyJobs = new ArrayList<>();
            int bucketIndex = (int) (currentTick % wheelSize);

            Bucket bucket = wheels[0].get(bucketIndex);
            List<Job> jobs = bucket.drain();
            readyJobs.addAll(jobs);

            for (Job job : jobs) {
                jobPositions.remove(job.getId());
            }

            if (currentTick > 0 && currentTick % wheelSize == 0) {
                cascade(1);
            }

            currentTick++;
            logger.debug("Tick {}: {} jobs ready", currentTick, readyJobs.size());

            return readyJobs;
        } finally {
            lock.unlock();
        }
    }

    private void cascade(int wheelLevel) {
        if (wheelLevel >= wheels.length)
            return;

        int bucketIndex = (int) ((currentTick / (long) Math.pow(wheelSize, wheelLevel)) % wheelSizes[wheelLevel]);
        Bucket bucket = wheels[wheelLevel].get(bucketIndex);
        List<Job> jobs = bucket.drain();

        for (Job job : jobs) {
            jobPositions.remove(job.getId());
            addJob(job);
        }

        if (currentTick % (wheelSize * wheelSizes[wheelLevel]) == 0) {
            cascade(wheelLevel + 1);
        }
    }

    private int determineWheelLevel(long delaySeconds) {
        for (int i = 0; i < wheelDurations.length; i++) {
            if (delaySeconds < wheelDurations[i] * wheelSizes[i]) {
                return i;
            }
        }
        return wheelDurations.length - 1;
    }

    public boolean removeJob(Long jobId) {
        lock.lock();
        try {
            WheelPosition pos = jobPositions.remove(jobId);
            if (pos == null)
                return false;

            Bucket bucket = wheels[pos.level].get(pos.bucket);
            return bucket.remove(jobId);
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try {
            return jobPositions.size();
        } finally {
            lock.unlock();
        }
    }

    public void clear() {
        lock.lock();
        try {
            for (List<Bucket> wheel : wheels) {
                for (Bucket bucket : wheel) {
                    bucket.clear();
                }
            }
            jobPositions.clear();
            currentTick = 0;
        } finally {
            lock.unlock();
        }
    }

    private static class Bucket {
        private final List<Job> jobs = new ArrayList<>();

        synchronized void add(Job job) {
            jobs.add(job);
        }

        synchronized boolean remove(Long jobId) {
            return jobs.removeIf(j -> j.getId().equals(jobId));
        }

        synchronized List<Job> drain() {
            List<Job> drained = new ArrayList<>(jobs);
            jobs.clear();
            return drained;
        }

        synchronized void clear() {
            jobs.clear();
        }
    }

    private static class WheelPosition {
        final int level;
        final int bucket;

        WheelPosition(int level, int bucket) {
            this.level = level;
            this.bucket = bucket;
        }
    }
}

package com.chronos.config;

import java.io.IOException;
import java.io.InputStream;
import java.util.Properties;

public class ChronosConfig {
    private final Properties properties;

    public ChronosConfig(String configFile) throws IOException {
        properties = new Properties();
        try (InputStream input = getClass().getClassLoader().getResourceAsStream(configFile)) {
            if (input == null) {
                throw new IOException("Unable to find " + configFile);
            }
            properties.load(input);
        }
    }

    public ChronosConfig(Properties properties) {
        this.properties = properties;
    }

    public String getDbUrl() {
        return properties.getProperty("db.url", "jdbc:postgresql://localhost:5432/chronos");
    }

    public String getDbUsername() {
        return properties.getProperty("db.username", "postgres");
    }

    public String getDbPassword() {
        return properties.getProperty("db.password", "postgres");
    }

    public String getNodeId() {
        return properties.getProperty("node.id", "node-" + System.currentTimeMillis());
    }

    public int getShardStart() {
        return Integer.parseInt(properties.getProperty("node.shard.start", "0"));
    }

    public int getShardEnd() {
        return Integer.parseInt(properties.getProperty("node.shard.end", "9"));
    }

    public int getTimingWheelTickSeconds() {
        return Integer.parseInt(properties.getProperty("timingwheel.tick.seconds", "1"));
    }

    public int getTimingWheelSize() {
        return Integer.parseInt(properties.getProperty("timingwheel.size", "60"));
    }

    public int getFetchWindowMinutes() {
        return Integer.parseInt(properties.getProperty("fetch.window.minutes", "10"));
    }

    public int getFetchBatchSize() {
        return Integer.parseInt(properties.getProperty("fetch.batch.size", "1000"));
    }

    public int getMaxConcurrentJobsPerTenant() {
        return Integer.parseInt(properties.getProperty("executor.max.concurrent.per.tenant", "100"));
    }

    public int getHeartbeatTimeoutSeconds() {
        return Integer.parseInt(properties.getProperty("heartbeat.timeout.seconds", "45"));
    }

    public int getReaperScanIntervalSeconds() {
        return Integer.parseInt(properties.getProperty("reaper.scan.interval.seconds", "30"));
    }

    public int getNodeHeartbeatIntervalSeconds() {
        return Integer.parseInt(properties.getProperty("node.heartbeat.interval.seconds", "10"));
    }

    public int getGrpcPort() {
        return Integer.parseInt(properties.getProperty("grpc.port", "50051"));
    }
}

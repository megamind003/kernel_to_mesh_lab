package com.chronos;

import com.chronos.config.ChronosConfig;
import com.chronos.database.JobRepository;
import com.chronos.model.Job;
import com.chronos.model.JobType;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.BufferedReader;
import java.io.FileReader;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.Properties;

public class StressTestLoader {

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("Usage: java StressTestLoader <creditcard.csv>");
            System.exit(1);
        }

        String csvPath = args[0];

        Properties props = new Properties();
        props.setProperty("db.url", "jdbc:postgresql://localhost:5432/chronos");
        props.setProperty("db.username", "postgres");
        props.setProperty("db.password", "postgres");

        ChronosConfig config = new ChronosConfig(props);
        JobRepository repository = new JobRepository(
                config.getDbUrl(),
                config.getDbUsername(),
                config.getDbPassword());

        repository.initializeSchema();

        System.out.println("Loading jobs from " + csvPath);

        ObjectMapper mapper = new ObjectMapper();
        int count = 0;
        long startTime = System.currentTimeMillis();

        try (BufferedReader br = new BufferedReader(new FileReader(csvPath))) {
            String header = br.readLine();
            if (header == null) {
                System.err.println("Empty CSV file");
                System.exit(1);
            }

            String line;
            while ((line = br.readLine()) != null) {
                String[] fields = line.split(",");
                if (fields.length < 2)
                    continue;

                try {
                    double timeSeconds = Double.parseDouble(fields[0].replace("\"", ""));
                    long delaySeconds = (long) timeSeconds;

                    Instant scheduledAt = Instant.now().plusSeconds(delaySeconds);

                    ObjectNode payload = mapper.createObjectNode();
                    payload.put("url", "http://localhost:8080/webhook");
                    payload.put("method", "POST");
                    ObjectNode body = mapper.createObjectNode();
                    body.put("transaction_id", count);
                    body.put("time", timeSeconds);
                    if (fields.length > 1) {
                        body.put("amount", fields[1]);
                    }
                    payload.set("body", body);

                    Job job = new Job(scheduledAt, JobType.WEBHOOK, payload.toString(), "stress-test");
                    repository.insertJob(job);

                    count++;

                    if (count % 10000 == 0) {
                        System.out.printf("Loaded %d jobs...%n", count);
                    }

                } catch (NumberFormatException e) {
                    System.err.println("Skipping invalid line: " + line);
                }
            }
        }

        long endTime = System.currentTimeMillis();
        long duration = endTime - startTime;

        System.out.printf("%nStress test data loaded successfully:%n");
        System.out.printf("Total jobs: %d%n", count);
        System.out.printf("Load time: %d ms%n", duration);
        System.out.printf("Jobs per second: %.2f%n", (count * 1000.0) / duration);

        repository.close();
    }
}

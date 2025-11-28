package com.fabrik.loadgen;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.client.RestTemplate;
import org.springframework.context.annotation.Bean;
import java.util.Random;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@SpringBootApplication
@EnableScheduling
public class LoadGeneratorApplication {

    private static final Logger logger = LoggerFactory.getLogger(LoadGeneratorApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(LoadGeneratorApplication.class, args);
    }

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }

    private final RestTemplate restTemplate = new RestTemplate();
    private final Random random = new Random();
    private final String frontendUrl = System.getenv().getOrDefault("FRONTEND_URL", "http://frontend:8080");

    @Scheduled(fixedRate = 1000)
    public void generateLoad() {
        try {
            // Jitter: random sleep 0-2s to avoid perfectly regular pattern
            Thread.sleep(random.nextInt(2000));

            // Randomly choose between read-heavy and write-heavy patterns
            int pattern = random.nextInt(100);

            if (pattern < 50) {
                // Read-heavy: multiple queries of current orders
                int reads = 1 + random.nextInt(5);
                for (int i = 0; i < reads; i++) {
                    restTemplate.getForObject(frontendUrl + "/", String.class);
                }
            } else {
                // Write path: place one or more orders
                int writes = 1 + random.nextInt(3);
                for (int i = 0; i < writes; i++) {
                    String item = "Item-" + random.nextInt(500);
                    int quantity = 1 + random.nextInt(5);
                    restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
                }
            }

            // Occasionally spike load to simulate bursts
            if (random.nextInt(100) < 5) { // ~5% of the time
                for (int i = 0; i < 10; i++) {
                    String item = "Promo-" + random.nextInt(1000);
                    int quantity = 1 + random.nextInt(10);
                    restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
                }
            }

            logger.info("Generated variable load pattern at {}", System.currentTimeMillis());
        } catch (Exception e) {
            logger.error("Error generating load: {}", e.getMessage());
        }
    }
}

package com.fabrik.fabproxy;

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
public class FabProxyApplication {

    private static final Logger logger = LoggerFactory.getLogger(FabProxyApplication.class);

    public static void main(String[] args) {
        SpringApplication.run(FabProxyApplication.class, args);
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

            int totalRequests = 0;
            int successfulRequests = 0;
            int failedRequests = 0;

            // Randomly choose between read-heavy and write-heavy patterns
            int pattern = random.nextInt(100);

            if (pattern < 50) {
                // Read-heavy: multiple queries of current orders
                int reads = 1 + random.nextInt(5);
                for (int i = 0; i < reads; i++) {
                    totalRequests++;
                    try {
                        String response = restTemplate.getForObject(frontendUrl + "/", String.class);
                        successfulRequests++;
                        logger.debug("GET / response: {}", response != null ? "OK" : "null");
                    } catch (Exception e) {
                        failedRequests++;
                        logger.warn("GET / failed: {}", e.getMessage());
                    }
                }
            } else {
                // Write path: place one or more orders
                int writes = 1 + random.nextInt(3);
                for (int i = 0; i < writes; i++) {
                    totalRequests++;
                    try {
                        String item = "Item-" + random.nextInt(500);
                        int quantity = 1 + random.nextInt(5);
                        String response = restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
                        successfulRequests++;
                        logger.debug("POST /order response: {}", response != null ? "OK" : "null");
                    } catch (Exception e) {
                        failedRequests++;
                        logger.warn("POST /order failed: {}", e.getMessage());
                    }
                }
            }

            // Occasionally spike load to simulate bursts
            if (random.nextInt(100) < 5) { // ~5% of the time
                for (int i = 0; i < 10; i++) {
                    totalRequests++;
                    try {
                        String item = "Promo-" + random.nextInt(1000);
                        int quantity = 1 + random.nextInt(10);
                        String response = restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
                        successfulRequests++;
                        logger.debug("POST /order (spike) response: {}", response != null ? "OK" : "null");
                    } catch (Exception e) {
                        failedRequests++;
                        logger.warn("POST /order (spike) failed: {}", e.getMessage());
                    }
                }
            }

            // Occasionally place high-quantity order to trigger validation exception (for Live Debugging demo)
            if (random.nextInt(100) < 2) { // ~2% of the time
                totalRequests++;
                try {
                    String item = "Bulk-" + random.nextInt(100);
                    int quantity = 150 + random.nextInt(100); // 150-249, exceeds max of 100
                    logger.info("Placing high-quantity order: {} x {} (will trigger validation)", item, quantity);
                    String response = restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
                    successfulRequests++;
                } catch (Exception e) {
                    failedRequests++;
                    logger.debug("High-quantity order failed as expected: {}", e.getMessage());
                }
            }

            logger.info("Load generation: {} total, {} successful, {} failed requests at {}",
                       totalRequests, successfulRequests, failedRequests, System.currentTimeMillis());

        } catch (Exception e) {
            logger.error("Critical error in load generation: {}", e.getMessage(), e);
        }
    }
}

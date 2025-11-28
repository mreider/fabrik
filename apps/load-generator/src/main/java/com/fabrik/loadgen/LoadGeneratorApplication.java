package com.fabrik.loadgen;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.client.RestTemplate;
import org.springframework.context.annotation.Bean;
import java.util.Random;

@SpringBootApplication
@EnableScheduling
public class LoadGeneratorApplication {

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
            // 1. Get orders
            restTemplate.getForObject(frontendUrl + "/", String.class);
            
            // 2. Place order
            String item = "Item-" + random.nextInt(100);
            int quantity = random.nextInt(10) + 1;
            restTemplate.postForObject(frontendUrl + "/order?item=" + item + "&quantity=" + quantity, null, String.class);
            
            System.out.println("Generated load: " + item);
        } catch (Exception e) {
            System.err.println("Error generating load: " + e.getMessage());
        }
    }
}

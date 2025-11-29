package com.fabrik.frontend;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import java.util.List;

@RestController
public class FrontendController {

    private final OrderRepository orderRepository;
    private final OrderClient orderClient;

    public FrontendController(OrderRepository orderRepository, OrderClient orderClient) {
        this.orderRepository = orderRepository;
        this.orderClient = orderClient;
    }

    @GetMapping("/")
    public ResponseEntity<List<OrderEntity>> getOrders() {
        // Check for failure injection
        String failureMode = System.getenv("FAILURE_MODE");
        String failureRateStr = System.getenv("FAILURE_RATE");
        boolean shouldFail = "true".equals(failureMode);

        if (!shouldFail && failureRateStr != null) {
            try {
                int rate = Integer.parseInt(failureRateStr);
                if (Math.random() * 100 < rate) {
                    shouldFail = true;
                }
            } catch (NumberFormatException e) {
                // Ignore invalid rate
            }
        }

        if (shouldFail) {
            try {
                // Simulate slow database query
                orderRepository.findAll();
                Thread.sleep(3000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore the find error, we want to throw HTTP 500
            }
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }

        return ResponseEntity.ok(orderRepository.findAll());
    }

    @PostMapping("/order")
    public ResponseEntity<String> placeOrder(@RequestParam String item, @RequestParam int quantity) {
        // Check for failure injection
        String failureMode = System.getenv("FAILURE_MODE");
        String failureRateStr = System.getenv("FAILURE_RATE");
        boolean shouldFail = "true".equals(failureMode);

        if (!shouldFail && failureRateStr != null) {
            try {
                int rate = Integer.parseInt(failureRateStr);
                if (Math.random() * 100 < rate) {
                    shouldFail = true;
                }
            } catch (NumberFormatException e) {
                // Ignore invalid rate
            }
        }

        if (shouldFail) {
            try {
                Thread.sleep(2000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Internal Server Error: Unable to process order due to system overload");
        }

        String result = orderClient.placeOrder(item, quantity);
        return ResponseEntity.ok(result);
    }
}

package com.fabrik.fulfillment;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/fulfillment")
public class FulfillmentController {

    private static final Logger logger = LoggerFactory.getLogger(FulfillmentController.class);
    private final OrderRepository orderRepository;

    public FulfillmentController(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    // GET /api/fulfillment/orders - List orders being processed (medium: ~60-120ms)
    @GetMapping("/orders")
    public ResponseEntity<List<OrderEntity>> listOrders() {
        simulateLatency(60, 120);
        return ResponseEntity.ok(orderRepository.findAll());
    }

    // GET /api/fulfillment/orders/{id} - Get specific order status (fast: ~15-35ms)
    @GetMapping("/orders/{id}")
    public ResponseEntity<OrderEntity> getOrder(@PathVariable String id) {
        simulateLatency(15, 35);
        return orderRepository.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // GET /api/fulfillment/queue - Orders pending fraud check (medium: ~80-150ms)
    @GetMapping("/queue")
    public ResponseEntity<List<OrderEntity>> getQueue() {
        simulateLatency(80, 150);
        return ResponseEntity.ok(orderRepository.findByStatus("PENDING"));
    }

    // GET /api/fulfillment/flagged - Orders flagged for fraud (medium: ~70-140ms)
    @GetMapping("/flagged")
    public ResponseEntity<List<OrderEntity>> getFlaggedOrders() {
        simulateLatency(70, 140);
        return ResponseEntity.ok(orderRepository.findByStatus("FRAUD_DETECTED"));
    }

    // GET /api/fulfillment/passed - Orders that passed fraud check (medium: ~70-140ms)
    @GetMapping("/passed")
    public ResponseEntity<List<OrderEntity>> getPassedOrders() {
        simulateLatency(70, 140);
        return ResponseEntity.ok(orderRepository.findByStatus("FRAUD_CHECK_PASSED"));
    }

    // GET /api/fulfillment/stats - Fulfillment statistics (slow: ~200-400ms)
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getStats() {
        simulateLatency(200, 400);
        List<OrderEntity> orders = orderRepository.findAll();

        Map<String, Object> stats = new HashMap<>();
        stats.put("totalOrders", orders.size());
        stats.put("pending", orders.stream().filter(o -> "PENDING".equals(o.getStatus())).count());
        stats.put("fraudDetected", orders.stream().filter(o -> "FRAUD_DETECTED".equals(o.getStatus())).count());
        stats.put("passed", orders.stream().filter(o -> "FRAUD_CHECK_PASSED".equals(o.getStatus())).count());
        stats.put("statusDistribution", orders.stream()
            .collect(Collectors.groupingBy(OrderEntity::getStatus, Collectors.counting())));

        return ResponseEntity.ok(stats);
    }

    // PUT /api/fulfillment/orders/{id}/review - Manual review override (slow: ~150-300ms)
    @PutMapping("/orders/{id}/review")
    public ResponseEntity<OrderEntity> reviewOrder(@PathVariable String id, @RequestBody Map<String, String> request) {
        simulateLatency(150, 300);
        String newStatus = request.getOrDefault("status", "FRAUD_CHECK_PASSED");

        return orderRepository.findById(id)
            .map(order -> {
                order.setStatus(newStatus);
                orderRepository.save(order);
                logger.info("Order {} manually reviewed, new status: {}", id, newStatus);
                return ResponseEntity.ok(order);
            })
            .orElse(ResponseEntity.notFound().build());
    }

    // POST /api/fulfillment/batch-process - Trigger batch processing (very slow: ~400-800ms)
    @PostMapping("/batch-process")
    public ResponseEntity<Map<String, Object>> batchProcess() {
        simulateLatency(400, 800);
        List<OrderEntity> pending = orderRepository.findByStatus("PENDING");

        int processed = 0;
        int flagged = 0;
        for (OrderEntity order : pending) {
            if (Math.random() > 0.9) {
                order.setStatus("FRAUD_DETECTED");
                flagged++;
            } else {
                order.setStatus("FRAUD_CHECK_PASSED");
            }
            orderRepository.save(order);
            processed++;
        }

        Map<String, Object> result = new HashMap<>();
        result.put("processed", processed);
        result.put("flagged", flagged);
        result.put("passed", processed - flagged);

        logger.info("Batch processed {} orders, {} flagged", processed, flagged);
        return ResponseEntity.ok(result);
    }

    private void simulateLatency(int minMs, int maxMs) {
        try {
            int delay = minMs + (int)(Math.random() * (maxMs - minMs));
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

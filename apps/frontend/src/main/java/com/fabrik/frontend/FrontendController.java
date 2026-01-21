package com.fabrik.frontend;

import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.stream.Collectors;

@RestController
public class FrontendController {

    private static final Logger logger = LoggerFactory.getLogger(FrontendController.class);
    private final OrderRepository orderRepository;
    private final OrderClient orderClient;

    @PersistenceContext
    private EntityManager entityManager;

    public FrontendController(OrderRepository orderRepository, OrderClient orderClient) {
        this.orderRepository = orderRepository;
        this.orderClient = orderClient;
    }

    // GET / - Main page listing orders (medium: ~50-150ms)
    @GetMapping("/")
    public ResponseEntity<List<OrderEntity>> getOrders() {
        simulateLatency(50, 150);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
        applyDbSlowdown();
        return ResponseEntity.ok(orderRepository.findAll());
    }

    // GET /health-check - Simple health endpoint (fast: ~5-15ms)
    @GetMapping("/health-check")
    public ResponseEntity<Map<String, String>> healthCheck() {
        simulateLatency(5, 15);
        Map<String, String> health = new HashMap<>();
        health.put("status", "UP");
        health.put("service", "frontend");
        return ResponseEntity.ok(health);
    }

    // GET /dashboard - Dashboard summary (slow: ~200-400ms, aggregates from backend)
    @GetMapping("/dashboard")
    public ResponseEntity<Map<String, Object>> getDashboard() {
        simulateLatency(200, 400);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }

        Map<String, Object> dashboard = new HashMap<>();
        List<OrderEntity> orders = orderRepository.findAll();

        dashboard.put("totalOrders", orders.size());
        dashboard.put("ordersByStatus", orders.stream()
            .collect(Collectors.groupingBy(OrderEntity::getStatus, Collectors.counting())));
        dashboard.put("recentOrders", orders.stream()
            .sorted((a, b) -> b.getId().compareTo(a.getId()))
            .limit(5)
            .collect(Collectors.toList()));

        return ResponseEntity.ok(dashboard);
    }

    // GET /orders/search - Search orders by status (medium: ~80-180ms)
    @GetMapping("/orders/search")
    public ResponseEntity<List<OrderEntity>> searchOrders(@RequestParam(required = false) String status) {
        simulateLatency(80, 180);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }

        List<OrderEntity> orders = orderRepository.findAll();
        if (status != null && !status.isEmpty()) {
            orders = orders.stream()
                .filter(o -> status.equalsIgnoreCase(o.getStatus()))
                .collect(Collectors.toList());
        }
        return ResponseEntity.ok(orders);
    }

    // GET /orders/{id} - Get specific order (fast: ~20-50ms)
    @GetMapping("/orders/{id}")
    public ResponseEntity<OrderEntity> getOrder(@PathVariable String id) {
        simulateLatency(20, 50);
        return orderRepository.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // POST /order - Place new order (existing, with failure injection)
    @PostMapping("/order")
    public ResponseEntity<String> placeOrder(@RequestParam String item, @RequestParam int quantity) {
        simulateLatency(30, 80);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Internal Server Error: Unable to process order");
        }

        String result = orderClient.placeOrder(item, quantity);
        return ResponseEntity.ok(result);
    }

    // POST /checkout - Full checkout flow (slow: ~300-600ms, simulates multi-step process)
    @PostMapping("/checkout")
    public ResponseEntity<Map<String, Object>> checkout(@RequestBody Map<String, Object> cart) {
        simulateLatency(300, 600);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
        applyDbSlowdown();

        Map<String, Object> result = new HashMap<>();
        String item = (String) cart.getOrDefault("item", "unknown");
        int quantity = (Integer) cart.getOrDefault("quantity", 1);

        String orderId = orderClient.placeOrder(item, quantity);
        result.put("orderId", orderId);
        result.put("status", "CHECKOUT_COMPLETE");
        result.put("item", item);
        result.put("quantity", quantity);

        logger.info("Checkout completed for order: {}", orderId);
        return ResponseEntity.ok(result);
    }

    // GET /analytics - Analytics summary (very slow: ~500-1000ms)
    @GetMapping("/analytics")
    public ResponseEntity<Map<String, Object>> getAnalytics() {
        simulateLatency(500, 1000);
        if (checkFailure()) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(null);
        }
        applyDbSlowdown();

        Map<String, Object> analytics = new HashMap<>();
        List<OrderEntity> orders = orderRepository.findAll();

        analytics.put("totalOrders", orders.size());
        analytics.put("totalQuantity", orders.stream().mapToInt(OrderEntity::getQuantity).sum());
        analytics.put("averageQuantity", orders.isEmpty() ? 0 :
            orders.stream().mapToInt(OrderEntity::getQuantity).average().orElse(0));
        analytics.put("statusDistribution", orders.stream()
            .collect(Collectors.groupingBy(OrderEntity::getStatus, Collectors.counting())));
        analytics.put("itemDistribution", orders.stream()
            .collect(Collectors.groupingBy(OrderEntity::getItem, Collectors.counting())));

        return ResponseEntity.ok(analytics);
    }

    private boolean checkFailure() {
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
            String[] criticalErrors = {
                "CRITICAL: Upstream service 'orders-service' not responding - connection refused after 3 retry attempts. " +
                    "Circuit breaker triggered. Customer checkout flow interrupted",
                "ERROR: Request validation failed - malformed cart data detected. " +
                    "Expected JSON array for 'items', received null. Request rejected to prevent data corruption",
                "FATAL: Session token expired during checkout flow. User must re-authenticate. " +
                    "Cart contents preserved but payment authorization voided",
                "CRITICAL: Backend service dependency 'inventory-service' returned unexpected HTTP 503. " +
                    "Cannot verify product availability. Checkout blocked to prevent overselling",
                "ERROR: Request processing interrupted - downstream timeout from 'orders-service' after 30s. " +
                    "Order may have been partially created. Customer should verify order status before retry",
                "FATAL: Data serialization error - failed to parse order response from backend. " +
                    "Unexpected field 'promotionCode' with null value. Frontend-backend contract violation detected"
            };
            String error = criticalErrors[(int)(Math.random() * criticalErrors.length)];
            logger.error("Frontend request failed: {}", error);
        }

        return shouldFail;
    }

    private void applyDbSlowdown() {
        String dbSlowdownRateStr = System.getenv("DB_SLOWDOWN_RATE");
        String dbSlowdownDelayStr = System.getenv("DB_SLOWDOWN_DELAY");
        if (dbSlowdownRateStr != null && dbSlowdownDelayStr != null && entityManager != null) {
            try {
                int rate = Integer.parseInt(dbSlowdownRateStr);
                int delayMs = Integer.parseInt(dbSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    int iterations = delayMs * 5000;
                    logger.debug("Running DB computation with {} iterations", iterations);
                    entityManager.createNativeQuery(
                        "SELECT count(*) FROM generate_series(1, " + iterations + ") s, " +
                        "LATERAL (SELECT md5(CAST(random() AS text))) x"
                    ).getSingleResult();
                }
            } catch (Exception e) {
                logger.warn("DB slowdown failed: {}", e.getMessage());
            }
        }
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

package com.fabrik.frontend;

import org.springframework.web.bind.annotation.*;
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

    // POST /order - Place new order (calls downstream orders service)
    @PostMapping("/order")
    public ResponseEntity<String> placeOrder(@RequestParam String item, @RequestParam int quantity) {
        simulateLatency(30, 80);
        String result = orderClient.placeOrder(item, quantity);
        return ResponseEntity.ok(result);
    }

    // POST /checkout - Full checkout flow (slow: ~300-600ms, simulates multi-step process)
    @PostMapping("/checkout")
    public ResponseEntity<Map<String, Object>> checkout(@RequestBody Map<String, Object> cart) {
        simulateLatency(300, 600);
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

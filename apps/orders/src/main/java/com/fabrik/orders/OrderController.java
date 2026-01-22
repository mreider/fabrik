package com.fabrik.orders;

import com.fabrik.orders.dto.OrderRequest;
import com.fabrik.orders.dto.OrderResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.HashMap;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private static final Logger logger = LoggerFactory.getLogger(OrderController.class);
    private final OrderRepository orderRepository;
    private final KafkaProducerService kafkaProducerService;

    @PersistenceContext
    private EntityManager entityManager;

    public OrderController(OrderRepository orderRepository, KafkaProducerService kafkaProducerService) {
        this.orderRepository = orderRepository;
        this.kafkaProducerService = kafkaProducerService;
    }

    // GET /api/orders - List all orders (medium: ~100-200ms with simulated load)
    @GetMapping
    public ResponseEntity<List<OrderEntity>> listOrders() {
        simulateLatency(50, 150);
        return ResponseEntity.ok(orderRepository.findAll());
    }

    // GET /api/orders/{id} - Get specific order (fast: ~10-50ms)
    @GetMapping("/{id}")
    public ResponseEntity<OrderEntity> getOrder(@PathVariable String id) {
        simulateLatency(10, 40);
        return orderRepository.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // GET /api/orders/recent - Get recent orders (fast: ~20-80ms)
    @GetMapping("/recent")
    public ResponseEntity<List<OrderEntity>> getRecentOrders() {
        simulateLatency(20, 60);
        return ResponseEntity.ok(orderRepository.findTop10ByOrderByIdDesc());
    }

    // GET /api/orders/status/{status} - Filter by status (medium: ~80-200ms)
    @GetMapping("/status/{status}")
    public ResponseEntity<List<OrderEntity>> getOrdersByStatus(@PathVariable String status) {
        simulateLatency(80, 180);
        return ResponseEntity.ok(orderRepository.findByStatus(status));
    }

    // GET /api/orders/stats - Aggregation stats (slow: ~300-800ms)
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getOrderStats() {
        simulateLatency(300, 700);
        Map<String, Object> stats = new HashMap<>();
        stats.put("totalOrders", orderRepository.count());
        stats.put("ordersByStatus", orderRepository.findAll().stream()
            .collect(Collectors.groupingBy(OrderEntity::getStatus, Collectors.counting())));
        stats.put("totalQuantity", orderRepository.findAll().stream()
            .mapToInt(OrderEntity::getQuantity).sum());
        return ResponseEntity.ok(stats);
    }

    // PUT /api/orders/{id}/cancel - Cancel order (medium: ~100-250ms)
    @PutMapping("/{id}/cancel")
    public ResponseEntity<OrderResponse> cancelOrder(@PathVariable String id) {
        simulateLatency(100, 200);
        return orderRepository.findById(id)
            .map(order -> {
                order.setStatus("CANCELLED");
                orderRepository.save(order);
                kafkaProducerService.sendOrderUpdate(id, "CANCELLED");
                return ResponseEntity.ok(new OrderResponse(id, "CANCELLED"));
            })
            .orElse(ResponseEntity.notFound().build());
    }

    // POST /api/orders - Place new order (with DB-based chaos for proper root cause detection)
    @PostMapping
    public ResponseEntity<OrderResponse> placeOrder(@RequestBody OrderRequest request) {
        String orderId = UUID.randomUUID().toString();

        // DB Slowdown Chaos: Heavy PostgreSQL query that can timeout
        // When DB_SLOWDOWN_DELAY exceeds DB_QUERY_TIMEOUT_MS, this causes QueryTimeoutException
        // Davis will root-cause to: "Database call to PostgreSQL timed out"
        String dbSlowdownRateStr = System.getenv("DB_SLOWDOWN_RATE");
        String dbSlowdownDelayStr = System.getenv("DB_SLOWDOWN_DELAY");
        if (dbSlowdownRateStr != null && dbSlowdownDelayStr != null && entityManager != null) {
            try {
                int rate = Integer.parseInt(dbSlowdownRateStr);
                int delayMs = Integer.parseInt(dbSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Each iteration takes ~0.2ms, so multiply delay by 5000 to get approximate ms
                    int iterations = delayMs * 5000;
                    logger.info("Executing heavy DB query for order {} ({} iterations, ~{}ms expected)",
                        orderId.substring(0, 8), iterations, delayMs);
                    entityManager.createNativeQuery(
                        "SELECT count(*) FROM generate_series(1, " + iterations + ") s, " +
                        "LATERAL (SELECT md5(CAST(random() AS text))) x"
                    ).getSingleResult();
                    logger.debug("DB query completed for order {}", orderId.substring(0, 8));
                }
            } catch (Exception e) {
                // This exception (QueryTimeoutException or similar) is traceable by Davis
                logger.error("Database operation failed for order {}: {}", orderId.substring(0, 8), e.getMessage());
                throw new RuntimeException("Database query timeout - order " + orderId.substring(0, 8) + " could not be processed", e);
            }
        }
        String item = request.item();
        int quantity = request.quantity();

        OrderEntity order = new OrderEntity();
        order.setId(orderId);
        order.setItem(item);
        order.setQuantity(quantity);
        order.setStatus("PENDING");

        // Validate order - occasionally fails for demo/debugging purposes
        if (quantity > 100) {
            String errorMessage = String.format("Order validation failed: quantity %d exceeds maximum of 100 for item '%s'", quantity, item);
            logger.error("Validation error for order {}: {}", orderId, errorMessage);
            throw new IllegalArgumentException(errorMessage);
        }

        orderRepository.save(order);

        kafkaProducerService.sendOrder(orderId);

        return ResponseEntity.ok(new OrderResponse(orderId, "PENDING"));
    }

    // Helper to simulate variable latency for realistic performance profiles
    private void simulateLatency(int minMs, int maxMs) {
        try {
            int delay = minMs + (int)(Math.random() * (maxMs - minMs));
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

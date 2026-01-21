package com.fabrik.orders;

import com.fabrik.orders.dto.OrderRequest;
import com.fabrik.orders.dto.OrderResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import java.util.UUID;

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

    @PostMapping
    public ResponseEntity<OrderResponse> placeOrder(@RequestBody OrderRequest request) {
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
            throw new RuntimeException("org.springframework.dao.QueryTimeoutException: SQL [INSERT INTO orders ...]; Query timeout");
        }

        // Check for DB slowdown (creates proper Database categorization via heavy computation)
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

        String orderId = UUID.randomUUID().toString();
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
}

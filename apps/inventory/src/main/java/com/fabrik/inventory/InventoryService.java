package com.fabrik.inventory;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.Optional;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

@Service
public class InventoryService {

    private static final Logger logger = LoggerFactory.getLogger(InventoryService.class);
    private final InventoryRepository inventoryRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    @PersistenceContext
    private EntityManager entityManager;

    public InventoryService(InventoryRepository inventoryRepository, KafkaTemplate<String, String> kafkaTemplate) {
        this.inventoryRepository = inventoryRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "orders", groupId = "inventory-group")
    @Transactional
    public void handleOrder(String orderId) {
        // Apply message processing slowdown (before business logic)
        String msgSlowdownRateStr = System.getenv("MSG_SLOWDOWN_RATE");
        String msgSlowdownDelayStr = System.getenv("MSG_SLOWDOWN_DELAY");
        if (msgSlowdownRateStr != null && msgSlowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(msgSlowdownRateStr);
                int delayMs = Integer.parseInt(msgSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Create explicit messaging span for the slowdown so Dynatrace categorizes it as Messaging
                    Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.inventory");
                    Span msgSpan = tracer.spanBuilder("message deserialization")
                            .setSpanKind(SpanKind.CONSUMER)
                            .setAttribute("messaging.system", "kafka")
                            .setAttribute("messaging.operation.type", "process")
                            .setAttribute("messaging.destination.name", "orders")
                            .startSpan();
                    try (Scope scope = msgSpan.makeCurrent()) {
                        logger.debug("Simulating message processing delay: {}ms", delayMs);
                        Thread.sleep(delayMs);
                    } finally {
                        msgSpan.end();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore if message processing simulation fails
            }
        }

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
            String[] criticalErrors = {
                "CRITICAL: Inventory sync conflict detected - warehouse 'EAST-1' reports different quantity than database. " +
                    "DB: 47 units, WMS: 23 units for SKU. Halting reservation until reconciliation complete",
                "FATAL: Stock reservation failed - item already reserved by concurrent transaction. " +
                    "Optimistic locking exception. Order " + orderId + " cannot claim inventory. Customer may need to retry",
                "ERROR: Warehouse management system 'wms-connector' returned error - item location unknown. " +
                    "SKU exists in catalog but physical location not mapped. Fulfillment cannot proceed",
                "CRITICAL: Inventory below safety stock threshold - cannot fulfill order " + orderId + ". " +
                    "Available: 2 units, Requested: 5 units, Safety stock: 10 units. Reorder triggered but ETA unknown",
                "FATAL: Batch lot validation failed - item from lot #LOT-2024-0892 recalled by manufacturer. " +
                    "Order " + orderId + " contained recalled items. Customer notification required",
                "ERROR: Multi-warehouse inventory allocation failed - no single warehouse can fulfill order " + orderId + ". " +
                    "Split shipment not allowed for this product category. Order requires manual routing"
            };
            String error = criticalErrors[(int)(Math.random() * criticalErrors.length)];
            logger.error("Inventory processing failed for order {}: {}", orderId, error);
            throw new RuntimeException(error);
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

        // Simulate item ID extraction (in real app, message would be JSON)
        String itemId = "Item-" + (int)(Math.random() * 100);

        Span receiveSpan = Span.current();
        receiveSpan.setAttribute("messaging.operation.type", "receive");
        receiveSpan.setAttribute("messaging.system", "kafka");

        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.inventory");
        Span processSpan = tracer.spanBuilder("check inventory")
                .setSpanKind(SpanKind.CONSUMER)
                .setAttribute("messaging.operation.type", "process")
                .setAttribute("messaging.system", "kafka")
                .startSpan();

        try (Scope scope = processSpan.makeCurrent()) {
            Optional<InventoryItem> itemOpt = inventoryRepository.findById(itemId);
            InventoryItem item = itemOpt.orElse(new InventoryItem(itemId, 100)); // Default stock

            // Auto-replenish when stock gets low (demo purposes)
            if (item.getQuantity() <= 5) {
                logger.info("Auto-replenishing {} (was: {}, now: 100)", itemId, item.getQuantity());
                item.setQuantity(100);
            }

            if (item.getQuantity() > 0) {
                item.setQuantity(item.getQuantity() - 1);
                inventoryRepository.save(item);

                // Publish to inventory-reserved
                sendReservedEvent(orderId, itemId);
            } else {
                logger.warn("Out of stock for {}", itemId);
            }
        } finally {
            processSpan.end();
        }
    }

    private void sendReservedEvent(String orderId, String itemId) {
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.inventory");
        Span span = tracer.spanBuilder("publish inventory reserved")
                .setSpanKind(SpanKind.PRODUCER)
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "inventory-reserved")
                .setAttribute("messaging.operation.type", "publish")
                .startSpan();
        
        try (Scope scope = span.makeCurrent()) {
            kafkaTemplate.send("inventory-reserved", orderId + ":" + itemId);
        } finally {
            span.end();
        }
    }
}

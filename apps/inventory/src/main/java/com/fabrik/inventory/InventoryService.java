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

@Service
public class InventoryService {

    private static final Logger logger = LoggerFactory.getLogger(InventoryService.class);
    private final InventoryRepository inventoryRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

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
                float delaySec = Integer.parseInt(msgSlowdownDelayStr) / 1000.0f;
                if (Math.random() * 100 < rate) {
                    // Simulate message processing overhead (deserialization, validation, DLQ)
                    if (Math.random() < 0.7) {
                        inventoryRepository.processMessageBatch(delaySec);
                    } else {
                        inventoryRepository.processDlqMessages(delaySec * 0.8f);
                    }
                }
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
            try {
                // Simulate slow inventory lookup query
                inventoryRepository.findAll();
                Thread.sleep(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore the find error, we want to throw the specific timeout exception below
            }
            throw new RuntimeException("org.springframework.dao.QueryTimeoutException: PreparedStatementCallback; SQL [SELECT * FROM inventory_items ...]; Query timeout; nested exception is org.postgresql.util.PSQLException: ERROR: canceling statement due to user request");
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
            // Apply slowdown via business metrics update (realistic analytics processing)
            String slowdownRateStr = System.getenv("SLOWDOWN_RATE");
            String slowdownDelayStr = System.getenv("SLOWDOWN_DELAY");
            if (slowdownRateStr != null && slowdownDelayStr != null) {
                try {
                    int rate = Integer.parseInt(slowdownRateStr);
                    float delaySec = Integer.parseInt(slowdownDelayStr) / 1000.0f;
                    if (Math.random() * 100 < rate) {
                        inventoryRepository.updateBusinessMetrics(delaySec * 0.5f, delaySec);
                    }
                } catch (Exception e) {
                    // Ignore if business metrics update fails
                }
            }

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

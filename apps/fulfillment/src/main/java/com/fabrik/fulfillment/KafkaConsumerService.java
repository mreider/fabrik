package com.fabrik.fulfillment;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import java.util.Optional;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class KafkaConsumerService {

    private static final Logger logger = LoggerFactory.getLogger(KafkaConsumerService.class);
    private final OrderRepository orderRepository;

    public KafkaConsumerService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    @KafkaListener(topics = "orders", groupId = "fulfillment-group")
    public void consumeOrder(String orderId) {
        // Apply message processing slowdown (before business logic)
        String msgSlowdownRateStr = System.getenv("MSG_SLOWDOWN_RATE");
        String msgSlowdownDelayStr = System.getenv("MSG_SLOWDOWN_DELAY");
        if (msgSlowdownRateStr != null && msgSlowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(msgSlowdownRateStr);
                int delayMs = Integer.parseInt(msgSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Create explicit messaging span for the slowdown so Dynatrace categorizes it as Messaging
                    Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.fulfillment");
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
                "CRITICAL: Fraud detection service unreachable - connection to 'fraud-detector' timed out. " +
                    "Order " + orderId + " cannot be verified. Placing in manual review queue",
                "FATAL: Fraud rules engine returned inconclusive result - order " + orderId + " matches conflicting patterns. " +
                    "High velocity (12 orders/hour) but trusted device fingerprint. Human review required",
                "ERROR: Order " + orderId + " flagged by velocity check - shipping address used in 3 orders within 10 minutes. " +
                    "Potential fraud ring detected. All related orders suspended pending investigation",
                "CRITICAL: Payment verification failed for order " + orderId + " - CVV mismatch reported by payment processor. " +
                    "Card flagged for potential unauthorized use. Order blocked",
                "FATAL: Customer account anomaly detected - order " + orderId + " placed from new device in different country " +
                    "than billing address. Account temporarily locked pending 2FA verification",
                "ERROR: Fraud model feature extraction failed - customer purchase history unavailable. " +
                    "Order " + orderId + " scored with limited data. Confidence: LOW. Escalating to manual review"
            };
            String error = criticalErrors[(int)(Math.random() * criticalErrors.length)];
            logger.error("Fulfillment processing failed for order {}: {}", orderId, error);
            throw new RuntimeException(error);
        }

        // Treat the framework-created span as the "receive" span
        Span receiveSpan = Span.current();
        receiveSpan.setAttribute("messaging.operation.type", "receive");
        receiveSpan.setAttribute("messaging.system", "kafka");
        
        // Create a child span for the actual processing
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.fulfillment");
        Span processSpan = tracer.spanBuilder("fraud check")
                .setSpanKind(SpanKind.CONSUMER)
                .setAttribute("messaging.operation.type", "process")
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "orders")
                .startSpan();

        try (Scope scope = processSpan.makeCurrent()) {
            Optional<OrderEntity> orderOpt = orderRepository.findById(orderId);
            if (orderOpt.isPresent()) {
                OrderEntity order = orderOpt.get();
                // Simulate fraud check logic
                if (Math.random() > 0.9) {
                    order.setStatus("FRAUD_DETECTED");
                    logger.warn("Fraud detected for order: {}", orderId);
                } else {
                    order.setStatus("FRAUD_CHECK_PASSED");
                    logger.info("Fraud check passed for order: {}", orderId);
                }
                orderRepository.save(order);
            } else {
                logger.error("Order not found: {}", orderId);
            }
        } finally {
            processSpan.end();
        }
    }

    @KafkaListener(topics = "order-updates", groupId = "fulfillment-updates-group")
    public void consumeOrderUpdate(String message) {
        // Message format: orderId:status
        String[] parts = message.split(":");
        if (parts.length < 2) {
            logger.warn("Invalid order update message format: {}", message);
            return;
        }

        String orderId = parts[0];
        String newStatus = parts[1];

        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.fulfillment");
        Span processSpan = tracer.spanBuilder("process order update")
                .setSpanKind(SpanKind.CONSUMER)
                .setAttribute("messaging.operation.type", "process")
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "order-updates")
                .startSpan();

        try (Scope scope = processSpan.makeCurrent()) {
            // Simulate processing delay
            Thread.sleep(20 + (int)(Math.random() * 40));

            orderRepository.findById(orderId).ifPresent(order -> {
                String previousStatus = order.getStatus();
                order.setStatus(newStatus);
                orderRepository.save(order);
                logger.info("Order {} status updated: {} -> {}", orderId, previousStatus, newStatus);
            });
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            processSpan.end();
        }
    }
}

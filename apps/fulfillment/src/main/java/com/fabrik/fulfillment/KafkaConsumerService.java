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
    public void consume(String orderId) {
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
            throw new RuntimeException("org.springframework.dao.QueryTimeoutException: SQL [UPDATE orders ...]; Query timeout");
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
}

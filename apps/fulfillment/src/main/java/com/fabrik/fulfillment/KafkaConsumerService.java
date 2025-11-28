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

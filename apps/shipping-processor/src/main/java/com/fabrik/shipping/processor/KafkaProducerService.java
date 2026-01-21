package com.fabrik.shipping.processor;

import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

@Service
public class KafkaProducerService {

    private final KafkaTemplate<String, String> kafkaTemplate;

    public KafkaProducerService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public void sendShippingNotification(String shipmentId, String orderId, String trackingNumber, String status) {
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.shipping.processor");
        Span span = tracer.spanBuilder("publish shipping notification")
                .setSpanKind(SpanKind.PRODUCER)
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "shipping-notifications")
                .setAttribute("messaging.operation.type", "publish")
                .startSpan();

        try (Scope scope = span.makeCurrent()) {
            String message = String.format("%s:%s:%s:%s", shipmentId, orderId, trackingNumber, status);
            kafkaTemplate.send("shipping-notifications", message);
        } finally {
            span.end();
        }
    }

    public void sendShipmentStatusUpdate(String shipmentId, String oldStatus, String newStatus) {
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.shipping.processor");
        Span span = tracer.spanBuilder("publish shipment status update")
                .setSpanKind(SpanKind.PRODUCER)
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "shipment-updates")
                .setAttribute("messaging.operation.type", "publish")
                .startSpan();

        try (Scope scope = span.makeCurrent()) {
            String message = String.format("%s:%s:%s", shipmentId, oldStatus, newStatus);
            kafkaTemplate.send("shipment-updates", message);
        } finally {
            span.end();
        }
    }
}

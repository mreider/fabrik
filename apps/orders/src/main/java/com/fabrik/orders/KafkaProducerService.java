package com.fabrik.orders;

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

    public void sendOrder(String orderId) {
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.orders");
        Span span = tracer.spanBuilder("publish order")
                .setSpanKind(SpanKind.PRODUCER)
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "orders")
                .setAttribute("messaging.operation.type", "publish")
                .startSpan();
        
        try (Scope scope = span.makeCurrent()) {
            kafkaTemplate.send("orders", orderId);
        } finally {
            span.end();
        }
    }
}

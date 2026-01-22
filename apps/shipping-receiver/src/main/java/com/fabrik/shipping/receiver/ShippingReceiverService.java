package com.fabrik.shipping.receiver;

import com.fabrik.shipping.receiver.dto.ShipmentRequest;
import com.fabrik.shipping.receiver.dto.ShipmentResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class ShippingReceiverService {

    private static final Logger logger = LoggerFactory.getLogger(ShippingReceiverService.class);

    private final RestTemplate restTemplate;
    private final String shippingProcessorUrl;

    public ShippingReceiverService(RestTemplate restTemplate,
                                   @Value("${shipping-processor.service.url:http://shipping-processor:8080}") String shippingProcessorUrl) {
        this.restTemplate = restTemplate;
        this.shippingProcessorUrl = shippingProcessorUrl;
    }

    @KafkaListener(topics = "inventory-reserved", groupId = "shipping-group")
    public void receive(String message) {
        // Parse message early for error reporting (format: orderId:itemId)
        String[] parts = message.split(":");
        String orderId = parts.length > 0 ? parts[0] : "unknown";
        String itemId = parts.length > 1 ? parts[1] : "unknown";

        // Apply message processing slowdown (deserialization and validation)
        String msgSlowdownRateStr = System.getenv("MSG_SLOWDOWN_RATE");
        String msgSlowdownDelayStr = System.getenv("MSG_SLOWDOWN_DELAY");
        if (msgSlowdownRateStr != null && msgSlowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(msgSlowdownRateStr);
                int delayMs = Integer.parseInt(msgSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Create explicit messaging span for the slowdown so Dynatrace categorizes it as Messaging
                    Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.shipping.receiver");
                    Span msgSpan = tracer.spanBuilder("message deserialization")
                            .setSpanKind(SpanKind.CONSUMER)
                            .setAttribute("messaging.system", "kafka")
                            .setAttribute("messaging.operation.type", "process")
                            .setAttribute("messaging.destination.name", "inventory-reserved")
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

        // Note: shipping-receiver doesn't have database access
        // Failures will propagate from shipping-processor (which has DB-based chaos)

        // Apply slowdown via message queue performance analysis
        String slowdownRateStr = System.getenv("SLOWDOWN_RATE");
        String slowdownDelayStr = System.getenv("SLOWDOWN_DELAY");
        if (slowdownRateStr != null && slowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(slowdownRateStr);
                int delayMs = Integer.parseInt(slowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Wrap in messaging span so Dynatrace categorizes it as "Message processing"
                    Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.shipping.receiver");
                    Span slowSpan = tracer.spanBuilder("message queue analysis")
                            .setSpanKind(SpanKind.CONSUMER)
                            .setAttribute("messaging.system", "kafka")
                            .setAttribute("messaging.operation.type", "process")
                            .setAttribute("messaging.destination.name", "inventory-reserved")
                            .startSpan();
                    try (Scope scope = slowSpan.makeCurrent()) {
                        logger.debug("Simulating message queue performance analysis");
                        Thread.sleep(delayMs);
                    } finally {
                        slowSpan.end();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore if queue analysis simulation fails
            }
        }

        Span span = Span.current();
        span.setAttribute("messaging.operation.type", "receive");
        span.setAttribute("messaging.system", "kafka");

        logger.info("Received shipping request for order: {}", orderId);

        // Call Processor via REST
        ShipmentRequest request = new ShipmentRequest(orderId, itemId, 1);

        try {
            ShipmentResponse response = restTemplate.postForObject(
                shippingProcessorUrl + "/api/shipments",
                request,
                ShipmentResponse.class
            );
            if (response != null) {
                logger.info("Shipment processed: {}", response.trackingNumber());
            }
        } catch (Exception e) {
            logger.error("Failed to process shipment: {}", e.getMessage());
        }
    }
}

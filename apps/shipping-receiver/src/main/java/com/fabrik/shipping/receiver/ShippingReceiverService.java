package com.fabrik.shipping.receiver;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import net.devh.boot.grpc.client.inject.GrpcClient;
import com.fabrik.proto.ShippingServiceGrpc;
import com.fabrik.proto.ShipmentRequest;
import com.fabrik.proto.ShipmentResponse;
import io.opentelemetry.api.trace.Span;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class ShippingReceiverService {

    private static final Logger logger = LoggerFactory.getLogger(ShippingReceiverService.class);

    @GrpcClient("shipping-processor")
    private ShippingServiceGrpc.ShippingServiceBlockingStub shippingStub;

    @KafkaListener(topics = "inventory-reserved", groupId = "shipping-group")
    public void receive(String message) {
        // Apply message processing slowdown (deserialization and validation)
        String msgSlowdownRateStr = System.getenv("MSG_SLOWDOWN_RATE");
        String msgSlowdownDelayStr = System.getenv("MSG_SLOWDOWN_DELAY");
        if (msgSlowdownRateStr != null && msgSlowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(msgSlowdownRateStr);
                int delayMs = Integer.parseInt(msgSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Simulate message processing overhead (deserialization, validation, retry)
                    if (Math.random() < 0.6) {
                        // Batch processing delay (complex JSON deserialization)
                        logger.debug("Simulating message batch processing delay");
                        Thread.sleep(delayMs);
                    } else {
                        // DLQ processing delay (retry logic)
                        logger.debug("Simulating DLQ processing delay");
                        Thread.sleep((long)(delayMs * 0.9));
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
            try {
                Thread.sleep(3000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            throw new RuntimeException("Message processing failure: Unable to parse shipping message or connection timeout to shipping processor");
        }

        // Apply slowdown via message queue performance analysis (independent of failures)
        String slowdownRateStr = System.getenv("SLOWDOWN_RATE");
        String slowdownDelayStr = System.getenv("SLOWDOWN_DELAY");
        if (slowdownRateStr != null && slowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(slowdownRateStr);
                int delayMs = Integer.parseInt(slowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Simulate message queue performance analysis
                    logger.debug("Simulating message queue performance analysis");
                    Thread.sleep(delayMs);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore if queue analysis simulation fails
            }
        }

        // Message format: orderId:itemId
        String[] parts = message.split(":");
        String orderId = parts[0];
        String itemId = parts[1];

        Span span = Span.current();
        span.setAttribute("messaging.operation.type", "receive");
        span.setAttribute("messaging.system", "kafka");

        logger.info("Received shipping request for order: {}", orderId);

        // Call Processor via gRPC
        ShipmentRequest request = ShipmentRequest.newBuilder()
                .setOrderId(orderId)
                .setItem(itemId)
                .setQuantity(1)
                .build();

        try {
            ShipmentResponse response = shippingStub.shipOrder(request);
            logger.info("Shipment processed: {}", response.getTrackingNumber());
        } catch (Exception e) {
            logger.error("Failed to process shipment: {}", e.getMessage());
        }
    }
}

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

package com.fabrik.shipping.processor;

import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import com.fabrik.proto.ShippingServiceGrpc;
import com.fabrik.proto.ShipmentRequest;
import com.fabrik.proto.ShipmentResponse;
import io.opentelemetry.api.trace.Span;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@GrpcService
public class ShippingService extends ShippingServiceGrpc.ShippingServiceImplBase {

    private static final Logger logger = LoggerFactory.getLogger(ShippingService.class);
    private final ShipmentRepository shipmentRepository;

    public ShippingService(ShipmentRepository shipmentRepository) {
        this.shipmentRepository = shipmentRepository;
    }

    @Override
    public void shipOrder(ShipmentRequest request, StreamObserver<ShipmentResponse> responseObserver) {
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
                // Simulate slow shipment database operations
                shipmentRepository.findAll();
                Thread.sleep(4000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore the find error, we want to throw the specific timeout exception below
            }
            responseObserver.onError(new RuntimeException("org.springframework.dao.QueryTimeoutException: PreparedStatementCallback; SQL [INSERT INTO shipments ...]; Query timeout; nested exception is org.postgresql.util.PSQLException: ERROR: canceling statement due to user request"));
            return;
        }

        // Apply slowdown via shipping analytics (independent of failures)
        String slowdownRateStr = System.getenv("SLOWDOWN_RATE");
        String slowdownDelayStr = System.getenv("SLOWDOWN_DELAY");
        if (slowdownRateStr != null && slowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(slowdownRateStr);
                float delaySec = Integer.parseInt(slowdownDelayStr) / 1000.0f;
                if (Math.random() * 100 < rate) {
                    // Simulate random query timeout (10% of slowdowns)
                    if (Math.random() < 0.1) {
                        throw new org.springframework.dao.QueryTimeoutException("Connection timeout during analytics query");
                    }
                    shipmentRepository.generateShippingAnalytics(delaySec);
                }
            } catch (org.springframework.dao.QueryTimeoutException e) {
                throw e;
            } catch (Exception e) {
                // Ignore if analytics generation fails
            }
        }

        Span span = Span.current();
        span.setAttribute("messaging.operation.type", "process");
        span.setAttribute("messaging.system", "grpc"); // Or internal

        logger.info("Processing shipment for order: {}", request.getOrderId());
        
        Shipment shipment = new Shipment(request.getOrderId(), "SHIPPED");
        shipmentRepository.save(shipment);

        ShipmentResponse response = ShipmentResponse.newBuilder()
                .setShipmentId(shipment.getShipmentId())
                .setStatus(shipment.getStatus())
                .setTrackingNumber(shipment.getTrackingNumber())
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}

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

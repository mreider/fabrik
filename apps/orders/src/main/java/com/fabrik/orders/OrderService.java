package com.fabrik.orders;

import com.fabrik.proto.OrderRequest;
import com.fabrik.proto.OrderResponse;
import com.fabrik.proto.OrderServiceGrpc;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;
import java.util.UUID;

@GrpcService
public class OrderService extends OrderServiceGrpc.OrderServiceImplBase {

    private final OrderRepository orderRepository;
    private final KafkaProducerService kafkaProducerService;

    public OrderService(OrderRepository orderRepository, KafkaProducerService kafkaProducerService) {
        this.orderRepository = orderRepository;
        this.kafkaProducerService = kafkaProducerService;
    }

    @Override
    public void placeOrder(OrderRequest request, StreamObserver<OrderResponse> responseObserver) {
        String orderId = UUID.randomUUID().toString();
        
        OrderEntity order = new OrderEntity();
        order.setId(orderId);
        order.setItem(request.getItem());
        order.setQuantity(request.getQuantity());
        order.setStatus("PENDING");
        
        orderRepository.save(order);
        
        kafkaProducerService.sendOrder(orderId);
        
        OrderResponse response = OrderResponse.newBuilder()
                .setOrderId(orderId)
                .setStatus("PENDING")
                .build();
                
        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}

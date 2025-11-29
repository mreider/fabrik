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
                // Actually attempt a query that will timeout or fail
                // We use a native query to simulate a slow/locked table
                orderRepository.findAll(); 
                Thread.sleep(5000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } catch (Exception e) {
                // Ignore the find error, we want to throw the specific timeout exception below
            }
            throw new RuntimeException("org.springframework.dao.QueryTimeoutException: PreparedStatementCallback; SQL [INSERT INTO orders ...]; Query timeout; nested exception is org.postgresql.util.PSQLException: ERROR: canceling statement due to user request");
        }

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

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

        // Check for slowdown injection (independent of failures)
        String slowdownRateStr = System.getenv("SLOWDOWN_RATE");
        String slowdownDelayStr = System.getenv("SLOWDOWN_DELAY");
        boolean shouldSlowdown = false;
        int slowdownDelay = 0;

        if (slowdownRateStr != null && slowdownDelayStr != null) {
            try {
                int rate = Integer.parseInt(slowdownRateStr);
                slowdownDelay = Integer.parseInt(slowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    shouldSlowdown = true;
                }
            } catch (NumberFormatException e) {
                // Ignore invalid values
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

        // Apply slowdown via business logic procedures (realistic DB performance degradation)
        if (shouldSlowdown) {
            try {
                // Call business validation procedure (becomes slow during high load)
                float delaySec = slowdownDelay / 1000.0f;
                
                // Simulate random query timeout (10% of slowdowns)
                if (Math.random() < 0.1) {
                    throw new org.springframework.dao.QueryTimeoutException("Database connection pool exhausted during compliance check");
                }
                
                orderRepository.validateOrderCompliance(delaySec);
            } catch (org.springframework.dao.QueryTimeoutException e) {
                throw e; // Propagate timeout to create failed span
            } catch (Exception e) {
                // If business procedure fails, fallback to simple processing
                try {
                    Thread.sleep(slowdownDelay / 2);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                }
            }
        }

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

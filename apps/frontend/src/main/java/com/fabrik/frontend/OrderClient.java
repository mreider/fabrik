package com.fabrik.frontend;

import com.fabrik.proto.OrderRequest;
import com.fabrik.proto.OrderResponse;
import com.fabrik.proto.OrderServiceGrpc;
import net.devh.boot.grpc.client.inject.GrpcClient;
import org.springframework.stereotype.Service;

@Service
public class OrderClient {

    @GrpcClient("orders")
    private OrderServiceGrpc.OrderServiceBlockingStub orderServiceStub;

    public String placeOrder(String item, int quantity) {
        OrderResponse response = orderServiceStub.placeOrder(OrderRequest.newBuilder()
                .setItem(item)
                .setQuantity(quantity)
                .build());
        return response.getOrderId();
    }
}

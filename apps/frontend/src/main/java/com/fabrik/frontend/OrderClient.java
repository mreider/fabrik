package com.fabrik.frontend;

import com.fabrik.frontend.dto.OrderRequest;
import com.fabrik.frontend.dto.OrderResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class OrderClient {

    private final RestTemplate restTemplate;
    private final String ordersServiceUrl;

    public OrderClient(RestTemplate restTemplate,
                       @Value("${orders.service.url:http://orders:8080}") String ordersServiceUrl) {
        this.restTemplate = restTemplate;
        this.ordersServiceUrl = ordersServiceUrl;
    }

    public String placeOrder(String item, int quantity) {
        OrderRequest request = new OrderRequest(item, quantity);
        OrderResponse response = restTemplate.postForObject(
            ordersServiceUrl + "/api/orders",
            request,
            OrderResponse.class
        );
        return response != null ? response.orderId() : null;
    }
}

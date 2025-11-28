package com.fabrik.frontend;

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
public class FrontendController {

    private final OrderRepository orderRepository;
    private final OrderClient orderClient;

    public FrontendController(OrderRepository orderRepository, OrderClient orderClient) {
        this.orderRepository = orderRepository;
        this.orderClient = orderClient;
    }

    @GetMapping("/")
    public List<OrderEntity> getOrders() {
        return orderRepository.findAll();
    }

    @PostMapping("/order")
    public String placeOrder(@RequestParam String item, @RequestParam int quantity) {
        return orderClient.placeOrder(item, quantity);
    }
}

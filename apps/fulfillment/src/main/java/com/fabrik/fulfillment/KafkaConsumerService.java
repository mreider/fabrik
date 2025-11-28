package com.fabrik.fulfillment;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import java.util.Optional;

@Service
public class KafkaConsumerService {

    private final OrderRepository orderRepository;

    public KafkaConsumerService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    @KafkaListener(topics = "orders", groupId = "fulfillment-group")
    public void consume(String orderId) {
        Optional<OrderEntity> orderOpt = orderRepository.findById(orderId);
        if (orderOpt.isPresent()) {
            OrderEntity order = orderOpt.get();
            order.setStatus("FULFILLED");
            orderRepository.save(order);
            System.out.println("Fulfilled order: " + orderId);
        } else {
            System.out.println("Order not found: " + orderId);
        }
    }
}

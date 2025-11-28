package com.fabrik.inventory;

import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.Optional;
import io.opentelemetry.api.GlobalOpenTelemetry;
import io.opentelemetry.api.trace.Span;
import io.opentelemetry.api.trace.SpanKind;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.Scope;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class InventoryService {

    private static final Logger logger = LoggerFactory.getLogger(InventoryService.class);
    private final InventoryRepository inventoryRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;

    public InventoryService(InventoryRepository inventoryRepository, KafkaTemplate<String, String> kafkaTemplate) {
        this.inventoryRepository = inventoryRepository;
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "orders", groupId = "inventory-group")
    @Transactional
    public void handleOrder(String orderId) {
        // Simulate item ID extraction (in real app, message would be JSON)
        String itemId = "Item-" + (int)(Math.random() * 100); 
        
        Span receiveSpan = Span.current();
        receiveSpan.setAttribute("messaging.operation.type", "receive");
        receiveSpan.setAttribute("messaging.system", "kafka");

        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.inventory");
        Span processSpan = tracer.spanBuilder("check inventory")
                .setSpanKind(SpanKind.CONSUMER)
                .setAttribute("messaging.operation.type", "process")
                .setAttribute("messaging.system", "kafka")
                .startSpan();

        try (Scope scope = processSpan.makeCurrent()) {
            Optional<InventoryItem> itemOpt = inventoryRepository.findById(itemId);
            InventoryItem item = itemOpt.orElse(new InventoryItem(itemId, 100)); // Default stock
            
            if (item.getQuantity() > 0) {
                item.setQuantity(item.getQuantity() - 1);
                inventoryRepository.save(item);
                
                // Publish to inventory-reserved
                sendReservedEvent(orderId, itemId);
            } else {
                logger.warn("Out of stock for {}", itemId);
            }
        } finally {
            processSpan.end();
        }
    }

    private void sendReservedEvent(String orderId, String itemId) {
        Tracer tracer = GlobalOpenTelemetry.getTracer("com.fabrik.inventory");
        Span span = tracer.spanBuilder("publish inventory reserved")
                .setSpanKind(SpanKind.PRODUCER)
                .setAttribute("messaging.system", "kafka")
                .setAttribute("messaging.destination.name", "inventory-reserved")
                .setAttribute("messaging.operation.type", "publish")
                .startSpan();
        
        try (Scope scope = span.makeCurrent()) {
            kafkaTemplate.send("inventory-reserved", orderId + ":" + itemId);
        } finally {
            span.end();
        }
    }
}

package com.fabrik.shipping.processor;

import com.fabrik.shipping.processor.dto.ShipmentRequest;
import com.fabrik.shipping.processor.dto.ShipmentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/shipments")
public class ShippingController {

    private static final Logger logger = LoggerFactory.getLogger(ShippingController.class);
    private final ShipmentRepository shipmentRepository;
    private final KafkaProducerService kafkaProducerService;

    @PersistenceContext
    private EntityManager entityManager;

    public ShippingController(ShipmentRepository shipmentRepository, KafkaProducerService kafkaProducerService) {
        this.shipmentRepository = shipmentRepository;
        this.kafkaProducerService = kafkaProducerService;
    }

    // GET /api/shipments - List all shipments (medium: ~60-120ms)
    @GetMapping
    public ResponseEntity<List<Shipment>> listShipments() {
        simulateLatency(60, 120);
        return ResponseEntity.ok(shipmentRepository.findAll());
    }

    // GET /api/shipments/{id} - Get specific shipment (fast: ~15-40ms)
    @GetMapping("/{id}")
    public ResponseEntity<Shipment> getShipment(@PathVariable String id) {
        simulateLatency(15, 40);
        return shipmentRepository.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // GET /api/shipments/order/{orderId} - Get shipment by order ID (fast: ~20-50ms)
    @GetMapping("/order/{orderId}")
    public ResponseEntity<Shipment> getShipmentByOrder(@PathVariable String orderId) {
        simulateLatency(20, 50);
        return shipmentRepository.findByOrderId(orderId)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // GET /api/shipments/track/{trackingNumber} - Track by tracking number (fast: ~25-60ms)
    @GetMapping("/track/{trackingNumber}")
    public ResponseEntity<Map<String, Object>> trackShipment(@PathVariable String trackingNumber) {
        simulateLatency(25, 60);
        List<Shipment> shipments = shipmentRepository.findAll();
        return shipments.stream()
            .filter(s -> trackingNumber.equals(s.getTrackingNumber()))
            .findFirst()
            .map(s -> {
                Map<String, Object> tracking = new HashMap<>();
                tracking.put("trackingNumber", s.getTrackingNumber());
                tracking.put("status", s.getStatus());
                tracking.put("orderId", s.getOrderId());
                tracking.put("shipmentId", s.getShipmentId());
                return ResponseEntity.ok(tracking);
            })
            .orElse(ResponseEntity.notFound().build());
    }

    // GET /api/shipments/recent - Get recent shipments (medium: ~50-100ms)
    @GetMapping("/recent")
    public ResponseEntity<List<Shipment>> getRecentShipments() {
        simulateLatency(50, 100);
        return ResponseEntity.ok(shipmentRepository.findTop10ByOrderByShipmentIdDesc());
    }

    // GET /api/shipments/status/{status} - Filter by status (medium: ~70-140ms)
    @GetMapping("/status/{status}")
    public ResponseEntity<List<Shipment>> getByStatus(@PathVariable String status) {
        simulateLatency(70, 140);
        return ResponseEntity.ok(shipmentRepository.findByStatus(status));
    }

    // GET /api/shipments/stats - Shipping statistics (slow: ~200-400ms)
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getStats() {
        simulateLatency(200, 400);
        List<Shipment> shipments = shipmentRepository.findAll();

        Map<String, Object> stats = new HashMap<>();
        stats.put("totalShipments", shipments.size());
        stats.put("statusDistribution", shipments.stream()
            .collect(Collectors.groupingBy(Shipment::getStatus, Collectors.counting())));
        stats.put("shipped", shipments.stream().filter(s -> "SHIPPED".equals(s.getStatus())).count());
        stats.put("delivered", shipments.stream().filter(s -> "DELIVERED".equals(s.getStatus())).count());
        stats.put("inTransit", shipments.stream().filter(s -> "IN_TRANSIT".equals(s.getStatus())).count());

        return ResponseEntity.ok(stats);
    }

    // PUT /api/shipments/{id}/status - Update shipment status (medium: ~100-200ms)
    @PutMapping("/{id}/status")
    public ResponseEntity<Shipment> updateStatus(@PathVariable String id, @RequestBody Map<String, String> request) {
        simulateLatency(100, 200);
        String newStatus = request.getOrDefault("status", "IN_TRANSIT");

        return shipmentRepository.findById(id)
            .map(shipment -> {
                String oldStatus = shipment.getStatus();
                shipment.setStatus(newStatus);
                shipmentRepository.save(shipment);
                logger.info("Shipment {} status updated to: {}", id, newStatus);

                // Send status update notification
                kafkaProducerService.sendShipmentStatusUpdate(id, oldStatus, newStatus);

                return ResponseEntity.ok(shipment);
            })
            .orElse(ResponseEntity.notFound().build());
    }

    // POST /api/shipments - Create new shipment (existing, with failure injection)
    @PostMapping
    public ResponseEntity<ShipmentResponse> shipOrder(@RequestBody ShipmentRequest request) {
        simulateLatency(80, 160);

        // DB Slowdown Chaos: Heavy PostgreSQL query that can timeout
        // When DB_SLOWDOWN_DELAY exceeds DB_QUERY_TIMEOUT_MS, this causes QueryTimeoutException
        // Davis will root-cause to: "Database call to PostgreSQL timed out"
        String dbSlowdownRateStr = System.getenv("DB_SLOWDOWN_RATE");
        String dbSlowdownDelayStr = System.getenv("DB_SLOWDOWN_DELAY");
        if (dbSlowdownRateStr != null && dbSlowdownDelayStr != null && entityManager != null) {
            try {
                int rate = Integer.parseInt(dbSlowdownRateStr);
                int delayMs = Integer.parseInt(dbSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    int iterations = delayMs * 5000;
                    logger.info("Executing heavy DB query for order {} ({} iterations, ~{}ms expected)",
                        request.orderId(), iterations, delayMs);
                    entityManager.createNativeQuery(
                        "SELECT count(*) FROM generate_series(1, " + iterations + ") s, " +
                        "LATERAL (SELECT md5(CAST(random() AS text))) x"
                    ).getSingleResult();
                    logger.debug("DB query completed for order {}", request.orderId());
                }
            } catch (Exception e) {
                // This exception (QueryTimeoutException or similar) is traceable by Davis
                logger.error("Database operation failed for order {}: {}", request.orderId(), e.getMessage());
                throw new RuntimeException("Database query timeout - shipment for order " + request.orderId() + " could not be created", e);
            }
        }

        logger.info("Processing shipment for order: {}", request.orderId());

        Shipment shipment = new Shipment(request.orderId(), "SHIPPED");
        shipmentRepository.save(shipment);

        // Send notification for new shipment
        kafkaProducerService.sendShippingNotification(
            shipment.getShipmentId(),
            shipment.getOrderId(),
            shipment.getTrackingNumber(),
            shipment.getStatus()
        );

        return ResponseEntity.ok(new ShipmentResponse(
            shipment.getShipmentId(),
            shipment.getStatus(),
            shipment.getTrackingNumber()
        ));
    }

    // POST /api/shipments/batch-deliver - Batch update to delivered (very slow: ~400-800ms)
    @PostMapping("/batch-deliver")
    public ResponseEntity<Map<String, Object>> batchDeliver() {
        simulateLatency(400, 800);
        List<Shipment> shipped = shipmentRepository.findByStatus("SHIPPED");

        int updated = 0;
        for (Shipment shipment : shipped) {
            shipment.setStatus("DELIVERED");
            shipmentRepository.save(shipment);
            updated++;
        }

        Map<String, Object> result = new HashMap<>();
        result.put("updated", updated);
        result.put("status", "DELIVERED");

        logger.info("Batch delivered {} shipments", updated);
        return ResponseEntity.ok(result);
    }

    private void simulateLatency(int minMs, int maxMs) {
        try {
            int delay = minMs + (int)(Math.random() * (maxMs - minMs));
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

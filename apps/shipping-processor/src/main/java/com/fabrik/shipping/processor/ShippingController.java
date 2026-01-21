package com.fabrik.shipping.processor;

import com.fabrik.shipping.processor.dto.ShipmentRequest;
import com.fabrik.shipping.processor.dto.ShipmentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

@RestController
@RequestMapping("/api/shipments")
public class ShippingController {

    private static final Logger logger = LoggerFactory.getLogger(ShippingController.class);
    private final ShipmentRepository shipmentRepository;

    @PersistenceContext
    private EntityManager entityManager;

    public ShippingController(ShipmentRepository shipmentRepository) {
        this.shipmentRepository = shipmentRepository;
    }

    @PostMapping
    public ResponseEntity<ShipmentResponse> shipOrder(@RequestBody ShipmentRequest request) {
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

        if (shouldFail) {
            throw new RuntimeException("org.springframework.dao.QueryTimeoutException: PreparedStatementCallback; SQL [INSERT INTO shipments ...]; Query timeout");
        }

        // Check for DB slowdown (creates proper Database categorization via heavy computation)
        String dbSlowdownRateStr = System.getenv("DB_SLOWDOWN_RATE");
        String dbSlowdownDelayStr = System.getenv("DB_SLOWDOWN_DELAY");
        if (dbSlowdownRateStr != null && dbSlowdownDelayStr != null && entityManager != null) {
            try {
                int rate = Integer.parseInt(dbSlowdownRateStr);
                int delayMs = Integer.parseInt(dbSlowdownDelayStr);
                if (Math.random() * 100 < rate) {
                    // Heavy DB computation - actual DB CPU work that OneAgent categorizes as Database
                    int iterations = delayMs * 5000;
                    String sql = "SELECT count(*) FROM generate_series(1, " + iterations + ") s, LATERAL (SELECT md5(CAST(random() AS text))) x";
                    logger.info("Executing SQL: {}", sql);
                    entityManager.createNativeQuery(sql).getSingleResult();
                }
            } catch (Exception e) {
                logger.warn("DB slowdown failed: {}", e.getMessage());
            }
        }

        logger.info("Processing shipment for order: {}", request.orderId());

        Shipment shipment = new Shipment(request.orderId(), "SHIPPED");
        shipmentRepository.save(shipment);

        return ResponseEntity.ok(new ShipmentResponse(
            shipment.getShipmentId(),
            shipment.getStatus(),
            shipment.getTrackingNumber()
        ));
    }
}

package com.fabrik.shipping.processor;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface ShipmentRepository extends JpaRepository<Shipment, String> {

    List<Shipment> findByStatus(String status);

    Optional<Shipment> findByOrderId(String orderId);

    List<Shipment> findTop10ByOrderByShipmentIdDesc();
}

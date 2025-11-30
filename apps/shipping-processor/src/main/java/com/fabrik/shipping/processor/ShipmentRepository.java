package com.fabrik.shipping.processor;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface ShipmentRepository extends JpaRepository<Shipment, String> {

    @Query(value = "SELECT generate_shipping_analytics(:delaySec)", nativeQuery = true)
    String generateShippingAnalytics(@Param("delaySec") float delaySec);
}

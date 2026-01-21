package com.fabrik.orders;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface OrderRepository extends JpaRepository<OrderEntity, String> {

    @Query(value = "SELECT validate_order_compliance(:delaySec)", nativeQuery = true)
    String validateOrderCompliance(@Param("delaySec") float delaySec);
}

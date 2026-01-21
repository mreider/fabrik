package com.fabrik.orders;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;

public interface OrderRepository extends JpaRepository<OrderEntity, String> {

    List<OrderEntity> findByStatus(String status);

    List<OrderEntity> findTop10ByOrderByIdDesc();

    @Query(value = "SELECT validate_order_compliance(:delaySec)", nativeQuery = true)
    String validateOrderCompliance(@Param("delaySec") float delaySec);
}

package com.fabrik.frontend;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface OrderRepository extends JpaRepository<OrderEntity, String> {

    @Query(value = "SELECT calculate_fraud_score(:delayMs)", nativeQuery = true)
    String calculateFraudScore(@Param("delayMs") int delayMs);
}

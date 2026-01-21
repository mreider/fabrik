package com.fabrik.inventory;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface InventoryRepository extends JpaRepository<InventoryItem, String> {

    List<InventoryItem> findByQuantityLessThan(int quantity);

    @Query(value = "SELECT update_business_metrics(:minDelay, :maxDelay)", nativeQuery = true)
    String updateBusinessMetrics(@Param("minDelay") float minDelay, @Param("maxDelay") float maxDelay);

    @Query(value = "SELECT process_message_batch(:delaySec)", nativeQuery = true)
    String processMessageBatch(@Param("delaySec") float delaySec);

    @Query(value = "SELECT process_dlq_messages(:delaySec)", nativeQuery = true)
    String processDlqMessages(@Param("delaySec") float delaySec);
}

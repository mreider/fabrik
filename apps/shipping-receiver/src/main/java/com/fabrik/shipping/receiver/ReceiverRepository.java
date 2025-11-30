package com.fabrik.shipping.receiver;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface ReceiverRepository extends JpaRepository<ReceiverEntity, String> {

    @Query(value = "SELECT analyze_message_queue_performance(:delayMs)", nativeQuery = true)
    String analyzeMessageQueuePerformance(@Param("delayMs") int delayMs);

    @Query(value = "SELECT process_message_batch(:delaySec)", nativeQuery = true)
    String processMessageBatch(@Param("delaySec") float delaySec);

    @Query(value = "SELECT process_dlq_messages(:delaySec)", nativeQuery = true)
    String processDlqMessages(@Param("delaySec") float delaySec);
}
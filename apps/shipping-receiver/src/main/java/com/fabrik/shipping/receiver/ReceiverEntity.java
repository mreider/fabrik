package com.fabrik.shipping.receiver;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.util.UUID;

@Entity
@Table(name = "receiver_log")
public class ReceiverEntity {
    @Id
    private String id;

    private String orderId;
    private String status;

    public ReceiverEntity() {}

    public ReceiverEntity(String orderId, String status) {
        this.id = UUID.randomUUID().toString();
        this.orderId = orderId;
        this.status = status;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getOrderId() { return orderId; }
    public void setOrderId(String orderId) { this.orderId = orderId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
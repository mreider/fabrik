package com.fabrik.shipping.processor;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.util.UUID;

@Entity
@Table(name = "shipments")
public class Shipment {

    @Id
    private String shipmentId;
    private String orderId;
    private String status;
    private String trackingNumber;

    public Shipment() {}

    public Shipment(String orderId, String status) {
        this.shipmentId = UUID.randomUUID().toString();
        this.orderId = orderId;
        this.status = status;
        this.trackingNumber = "TRK-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
    }

    public String getShipmentId() { return shipmentId; }
    public String getOrderId() { return orderId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getTrackingNumber() { return trackingNumber; }
}

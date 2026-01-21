package com.fabrik.shipping.receiver.dto;

public record ShipmentResponse(String shipmentId, String status, String trackingNumber) {}

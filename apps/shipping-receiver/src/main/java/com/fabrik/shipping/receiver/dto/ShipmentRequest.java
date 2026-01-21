package com.fabrik.shipping.receiver.dto;

public record ShipmentRequest(String orderId, String item, int quantity) {}

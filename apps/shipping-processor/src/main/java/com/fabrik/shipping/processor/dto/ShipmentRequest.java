package com.fabrik.shipping.processor.dto;

public record ShipmentRequest(String orderId, String item, int quantity) {}

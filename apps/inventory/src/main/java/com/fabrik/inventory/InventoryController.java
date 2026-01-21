package com.fabrik.inventory;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

@RestController
@RequestMapping("/api/inventory")
public class InventoryController {

    private static final Logger logger = LoggerFactory.getLogger(InventoryController.class);
    private final InventoryRepository inventoryRepository;

    public InventoryController(InventoryRepository inventoryRepository) {
        this.inventoryRepository = inventoryRepository;
    }

    // GET /api/inventory - List all inventory items (medium: ~80-150ms)
    @GetMapping
    public ResponseEntity<List<InventoryItem>> listInventory() {
        simulateLatency(80, 150);
        return ResponseEntity.ok(inventoryRepository.findAll());
    }

    // GET /api/inventory/{sku} - Get specific item (fast: ~15-40ms)
    @GetMapping("/{sku}")
    public ResponseEntity<InventoryItem> getItem(@PathVariable String sku) {
        simulateLatency(15, 40);
        return inventoryRepository.findById(sku)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // POST /api/inventory/check - Check availability (fast: ~20-60ms)
    @PostMapping("/check")
    public ResponseEntity<Map<String, Object>> checkAvailability(@RequestBody Map<String, Object> request) {
        simulateLatency(20, 60);
        String sku = (String) request.get("sku");
        int requested = (Integer) request.getOrDefault("quantity", 1);

        Map<String, Object> result = new HashMap<>();
        result.put("sku", sku);
        result.put("requested", requested);

        return inventoryRepository.findById(sku)
            .map(item -> {
                result.put("available", item.getQuantity());
                result.put("canFulfill", item.getQuantity() >= requested);
                return ResponseEntity.ok(result);
            })
            .orElseGet(() -> {
                result.put("available", 0);
                result.put("canFulfill", false);
                return ResponseEntity.ok(result);
            });
    }

    // GET /api/inventory/low-stock - Get low stock items (slow: ~200-400ms)
    @GetMapping("/low-stock")
    public ResponseEntity<List<InventoryItem>> getLowStockItems() {
        simulateLatency(200, 400);
        return ResponseEntity.ok(inventoryRepository.findByQuantityLessThan(10));
    }

    // GET /api/inventory/stats - Inventory statistics (slow: ~300-600ms)
    @GetMapping("/stats")
    public ResponseEntity<Map<String, Object>> getInventoryStats() {
        simulateLatency(300, 600);
        List<InventoryItem> items = inventoryRepository.findAll();

        Map<String, Object> stats = new HashMap<>();
        stats.put("totalSkus", items.size());
        stats.put("totalQuantity", items.stream().mapToInt(InventoryItem::getQuantity).sum());
        stats.put("averageQuantity", items.isEmpty() ? 0 :
            items.stream().mapToInt(InventoryItem::getQuantity).average().orElse(0));
        stats.put("lowStockCount", items.stream().filter(i -> i.getQuantity() < 10).count());
        stats.put("outOfStockCount", items.stream().filter(i -> i.getQuantity() == 0).count());

        return ResponseEntity.ok(stats);
    }

    // PUT /api/inventory/{sku}/restock - Restock item (medium: ~100-200ms)
    @PutMapping("/{sku}/restock")
    public ResponseEntity<InventoryItem> restockItem(@PathVariable String sku, @RequestBody Map<String, Integer> request) {
        simulateLatency(100, 200);
        int quantity = request.getOrDefault("quantity", 50);

        return inventoryRepository.findById(sku)
            .map(item -> {
                item.setQuantity(item.getQuantity() + quantity);
                inventoryRepository.save(item);
                logger.info("Restocked {} with {} units, new quantity: {}", sku, quantity, item.getQuantity());
                return ResponseEntity.ok(item);
            })
            .orElseGet(() -> {
                InventoryItem newItem = new InventoryItem(sku, quantity);
                inventoryRepository.save(newItem);
                logger.info("Created new inventory item {} with {} units", sku, quantity);
                return ResponseEntity.ok(newItem);
            });
    }

    private void simulateLatency(int minMs, int maxMs) {
        try {
            int delay = minMs + (int)(Math.random() * (maxMs - minMs));
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }
}

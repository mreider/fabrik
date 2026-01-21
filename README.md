# Fabrik - E-Commerce Microservices Demo

A microservices demo application for demonstrating Dynatrace observability with realistic workloads, variable performance characteristics, and configurable chaos engineering.

## Architecture

```
                                    ┌─────────────────┐
                                    │    Frontend     │
                                    │   (Port 8080)   │
                                    └────────┬────────┘
                                             │ REST
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Orders Service                                  │
│                                (Port 8080)                                   │
│  Endpoints: /api/orders, /api/orders/{id}, /api/orders/recent,              │
│             /api/orders/status/{status}, /api/orders/stats, PUT /cancel     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │ Kafka Topics                     │
              │ • orders                         │
              │ • order-updates                  │
              ▼                                  ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Inventory Service  │              │ Fulfillment Service │
│    (Port 8082)      │              │    (Port 8080)      │
│                     │              │                     │
│ Consumes: orders    │              │ Consumes: orders,   │
│ Produces:           │              │   order-updates     │
│   inventory-reserved│              └─────────────────────┘
└──────────┬──────────┘
           │ Kafka: inventory-reserved
           ▼
┌─────────────────────┐              ┌─────────────────────┐
│ Shipping Receiver   │───REST──────▶│ Shipping Processor  │
│    (Port 8083)      │              │    (Port 8080)      │
│                     │              │                     │
│ Consumes:           │              │ Produces:           │
│   inventory-reserved│              │   shipping-         │
└─────────────────────┘              │   notifications,    │
                                     │   shipment-updates  │
                                     └─────────────────────┘
                                              │
                                              ▼
                                     ┌─────────────────────┐
                                     │    PostgreSQL       │
                                     │    (Port 5432)      │
                                     └─────────────────────┘
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 8080 | Web gateway, dashboard, checkout flow |
| Orders | 8080 | Order management, Kafka producer |
| Inventory | 8082 | Stock management, reservation handling |
| Fulfillment | 8080 | Fraud detection, order state tracking |
| Shipping Receiver | 8083 | Kafka consumer, forwards to processor |
| Shipping Processor | 8080 | Shipment creation, tracking |

## Kafka Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| orders | Orders | Inventory, Fulfillment | New order events |
| order-updates | Orders | Fulfillment | Order status changes |
| inventory-reserved | Inventory | Shipping Receiver | Stock reserved events |
| shipping-notifications | Shipping Processor | - | Shipment created events |
| shipment-updates | Shipping Processor | - | Shipment status changes |

## REST Endpoints

### Frontend
- `GET /` - List orders (50-150ms)
- `GET /health-check` - Health status (5-15ms)
- `GET /dashboard` - Dashboard summary (200-400ms)
- `GET /orders/search?status=` - Search orders (80-180ms)
- `GET /orders/{id}` - Get order (20-50ms)
- `POST /order` - Place order (30-80ms)
- `POST /checkout` - Full checkout (300-600ms)
- `GET /analytics` - Analytics (500-1000ms)

### Orders
- `GET /api/orders` - List all (50-150ms)
- `GET /api/orders/{id}` - Get order (10-40ms)
- `GET /api/orders/recent` - Recent orders (20-60ms)
- `GET /api/orders/status/{status}` - By status (80-180ms)
- `GET /api/orders/stats` - Statistics (300-700ms)
- `POST /api/orders` - Create order
- `PUT /api/orders/{id}/cancel` - Cancel (100-200ms)

### Inventory
- `GET /api/inventory` - List items (80-150ms)
- `GET /api/inventory/{sku}` - Get item (15-40ms)
- `POST /api/inventory/check` - Check availability (20-60ms)
- `GET /api/inventory/low-stock` - Low stock items (200-400ms)
- `GET /api/inventory/stats` - Statistics (300-600ms)
- `PUT /api/inventory/{sku}/restock` - Restock (100-200ms)

### Fulfillment
- `GET /api/fulfillment/orders` - List orders (60-120ms)
- `GET /api/fulfillment/orders/{id}` - Get order (15-35ms)
- `GET /api/fulfillment/queue` - Pending orders (80-150ms)
- `GET /api/fulfillment/flagged` - Fraud flagged (70-140ms)
- `GET /api/fulfillment/passed` - Passed checks (70-140ms)
- `GET /api/fulfillment/stats` - Statistics (200-400ms)
- `PUT /api/fulfillment/orders/{id}/review` - Manual review (150-300ms)
- `POST /api/fulfillment/batch-process` - Batch process (400-800ms)

### Shipping Processor
- `GET /api/shipments` - List shipments (60-120ms)
- `GET /api/shipments/{id}` - Get shipment (15-40ms)
- `GET /api/shipments/order/{orderId}` - By order (20-50ms)
- `GET /api/shipments/track/{tracking}` - Track (25-60ms)
- `GET /api/shipments/recent` - Recent (50-100ms)
- `GET /api/shipments/status/{status}` - By status (70-140ms)
- `GET /api/shipments/stats` - Statistics (200-400ms)
- `POST /api/shipments` - Create (80-160ms)
- `PUT /api/shipments/{id}/status` - Update status (100-200ms)
- `POST /api/shipments/batch-deliver` - Batch deliver (400-800ms)

## Chaos Engineering

An argo pod runs a chaos simulation loop that:
1. Waits a random 0-2 hours
2. Modifies deployment specs via `kubectl set env` to inject failure env vars
3. Runs 10 minutes of chaos (pods restart with failures enabled)
4. Removes env vars (pods restart back to normal)
5. Repeat

This creates K8s spec changes that Dynatrace can correlate with the resulting problems.

**Manual trigger:**
```bash
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual
```

**Environment variables** (set automatically by argo, or manually):

| Variable | Description |
|----------|-------------|
| `FAILURE_RATE=30` | Percentage of requests that throw exceptions |
| `FAILURE_MODE=true` | Enable 100% failure rate |
| `DB_SLOWDOWN_RATE=50` | Percentage of requests with DB slowdown |
| `DB_SLOWDOWN_DELAY=500` | DB slowdown duration in ms |
| `MSG_SLOWDOWN_RATE=25` | Percentage of Kafka messages with delay |
| `MSG_SLOWDOWN_DELAY=200` | Message processing delay in ms |

### Failure Scenarios

When failures occur, services log realistic error messages. Examples by service:

**Orders Service**
- Payment gateway declines (insufficient funds, card expired)
- Inventory reservation race conditions
- Kafka broker unavailable for event publishing
- Foreign key constraint violations

**Fulfillment Service**
- Fraud detection service timeouts
- Velocity check failures (too many orders from same address)
- CVV mismatch from payment processor
- Customer account anomalies (new device, different country)

**Inventory Service**
- Warehouse sync conflicts (database vs WMS mismatch)
- Stock reservation optimistic locking failures
- Items below safety stock threshold
- Batch lot recalls requiring order cancellation

**Shipping Receiver**
- Shipping processor service unavailable
- Carrier API rate limits exceeded
- Address validation failures (undeliverable)
- Hazmat compliance holds

**Shipping Processor**
- Carrier integration failures (FedEx, UPS API errors)
- Duplicate shipment idempotency violations
- Package weight validation mismatches
- Carrier account suspension

**Frontend**
- Upstream service circuit breakers open
- Session token expiration during checkout
- Request validation failures
- Backend service dependencies returning 503

## Deployment

Two Kubernetes manifests are provided:

- `k8s/fabrik-oa.yaml` - OneAgent instrumentation (no OTel sidecars)
- `k8s/fabrik-ot.yaml` - OpenTelemetry instrumentation (with OTel collector)

Deploy to separate namespaces:
```bash
kubectl apply -f k8s/fabrik-oa.yaml -n fabrik-oa
kubectl apply -f k8s/fabrik-ot.yaml -n fabrik-ot
```

## Performance Characteristics

Endpoints have variable latency to simulate realistic workloads:

- **Fast** (10-60ms): Simple lookups, health checks
- **Medium** (60-200ms): List operations, simple queries
- **Slow** (200-400ms): Aggregations, statistics
- **Very Slow** (400-1000ms): Complex analytics, batch operations

## Building

```bash
cd apps/<service>
./mvnw clean package -DskipTests
docker build -t fabrik/<service>:latest .
```

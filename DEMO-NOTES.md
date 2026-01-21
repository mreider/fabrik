# Fabrik Demo Notes

## Overview
This document captures demo setup details for Dynatrace features using the Fabrik demo application.

---

## 1. Response Time Breakdown Fix

### Problem
Response time breakdown was showing "Unclassified" instead of properly categorized time (Database, Outbound calls, etc.)

### Root Cause
- OneAgent categorizes based on `span.kind="client"` with appropriate attributes
- Client-side sleeps or fast DB queries don't create proper spans
- The **peer must actually respond slowly** to create proper client spans

### Solution
Deployed an internal "fraud-detection-api" service that uses httpbin's `/delay/{seconds}` endpoint:

**Service:** `fraud-detection-api` in `ext-services` namespace
- Uses `kennethreitz/httpbin` image
- Namespace labeled with `dynatrace.com/inject: "false"` (unmonitored)
- Services call `http://fraud-detection-api.ext-services/delay/{seconds}`

**Manifest:** `k8s/delay-service.yaml`

**Result:** Slowdowns now show as "Outbound calls" in response time breakdown with proper attribution.

### Configuration
Services use these env vars for slowdown:
- `SLOWDOWN_RATE` - percentage of requests to slow down (e.g., "50")
- `SLOWDOWN_DELAY` - delay in milliseconds (e.g., "6000")

---

## 2. Live Debugging Demo

### Setup
Added order validation in `OrderService.java` that throws an exception with interesting variables to watch.

**File:** `apps/orders/src/main/java/com/fabrik/orders/OrderService.java`
**Line:** ~89

```java
// Validate order - occasionally fails for demo/debugging purposes
if (quantity > 100) {
    String errorMessage = String.format("Order validation failed: quantity %d exceeds maximum of 100 for item '%s'", quantity, item);
    logger.error("Validation error for order {}: {}", orderId, errorMessage);
    throw new IllegalArgumentException(errorMessage);
}
```

### Variables to Watch at Breakpoint
- `orderId` - UUID of the order
- `item` - product name from request
- `quantity` - amount ordered (will be > 100)
- `order` - full OrderEntity object with all fields
- `errorMessage` - the formatted error string

### How to Trigger
**Automatic:** fab-proxy places high-quantity orders (~2% of cycles) with qty 150-249
**Manual:** Place an order with quantity > 100

### Live Debugging Steps
1. Open **Live Debugger** app in Dynatrace
2. Select the `orders` service in your namespace (fabrik-oa, fabrik-oa-2, or fabrik-ot)
3. Navigate to `OrderService.java` line 89 (the `throw` statement)
4. Click the gutter to add a **non-breaking breakpoint**
5. Optionally add condition: `quantity > 100`
6. Trigger the exception by placing an order with qty > 100
7. View snapshot in bottom pane:
   - All local variable values
   - Complete stack trace
   - Process information
   - Tracing context

### IDE Integration (Optional)
- **VS Code:** Install "Observability for Developers by Dynatrace" extension
- **JetBrains:** Install Dynatrace plugin
- Right-click line number → "Add Live Debugging Breakpoint"

### Documentation
- [Live Debugger — Dynatrace Docs](https://docs.dynatrace.com/docs/observe/application-observability/live-debugger)
- [Live Debugger breakpoints](https://docs.dynatrace.com/docs/observe/applications-and-microservices/developer-observability/offering-capabilities/breakpoints)
- [IDE Integration](https://docs.dynatrace.com/docs/observe/application-observability/live-debugger/ide-integration)

---

## 3. Namespaces & Deployments

### Monitored Namespaces (with Dynatrace)
- `fabrik-oa` - OneAgent monitored
- `fabrik-oa-2` - OneAgent monitored
- `fabrik-ot` - OpenTelemetry instrumented

### Unmonitored Namespace
- `ext-services` - contains fraud-detection-api (no Dynatrace injection)

### Key Manifests
- `k8s/fabrik-oa.yaml` - OneAgent namespace 1
- `k8s/fabrik-oa-2.yaml` - OneAgent namespace 2
- `k8s/fabrik-ot.yaml` - OpenTelemetry namespace
- `k8s/delay-service.yaml` - Fraud detection API (unmonitored)

---

## 4. Problem Patterns & Ripple Effect

### Ripple Effect for Root Cause Detection
The key demo pattern is the **ripple effect**:
1. `shipping-processor` calls `fraud-detection-api` (unmonitored, slow)
2. `shipping-receiver` calls `shipping-processor` via gRPC and waits
3. Dynatrace detects slowdown in `shipping-receiver` with root cause = `shipping-processor`

This creates proper response time categorization ("Outbound calls") AND root cause detection.

### Environment Variables

| Variable | Purpose | Shows As |
|----------|---------|----------|
| `SLOWDOWN_RATE` / `SLOWDOWN_DELAY` | Calls fraud-detection-api (slow peer) | "Outbound calls" |
| `DB_SLOWDOWN_RATE` / `DB_SLOWDOWN_DELAY` | Heavy DB computation | "Database" |
| `MSG_SLOWDOWN_RATE` / `MSG_SLOWDOWN_DELAY` | Messaging delays | "Unclassified" (variability) |
| `FAILURE_RATE` | % of requests that fail | Exception |
| `FAILURE_MODE=true` | Always fail | Exception |

### Current Configuration (fabrik-oa)
```yaml
# shipping-processor: Ripple effect source (calls fraud-detection-api)
SLOWDOWN_RATE: "50"      # 50% of requests
SLOWDOWN_DELAY: "6000"   # 6 seconds

# inventory: DB and messaging variability
DB_SLOWDOWN_RATE: "30"   # 30% of requests
DB_SLOWDOWN_DELAY: "2000" # 2 seconds of DB work
MSG_SLOWDOWN_RATE: "20"
MSG_SLOWDOWN_DELAY: "3000"

# fulfillment: Occasional failures + messaging variability
FAILURE_RATE: "5"        # 5% failure rate
MSG_SLOWDOWN_RATE: "20"
MSG_SLOWDOWN_DELAY: "3000"

# shipping-receiver: Messaging variability (also gets ripple from shipping-processor)
MSG_SLOWDOWN_RATE: "20"
MSG_SLOWDOWN_DELAY: "3000"
```

### Key Insight (from Christian)
> "We look at span.kind and if that is 'client' and we have a db.system field, we account it for DB queries.
> Unfortunately that is not easy to fake because you need an actual slow peer. A client-side sleep will not help."

That's why:
- **Outbound calls**: Use fraud-detection-api (actual slow peer response)
- **Database**: Use heavy computation queries (`generate_series` + `md5`)
- **Messaging**: Thread.sleep shows as "Unclassified" but provides variability for sorting

---

## 5. Current Status

### Completed
- [x] fraud-detection-api deployed in unmonitored namespace
- [x] shipping-processor calls fraud-detection-api for "Outbound calls" categorization
- [x] Validation exception in orders service (qty > 100) for Live Debugging
- [x] fab-proxy generates high-quantity orders (~2% of cycles)
- [x] Ripple effect: shipping-processor → shipping-receiver chain
- [x] DB slowdown via heavy computation (not useless findAll loops)

### To Rebuild & Redeploy
After code changes, rebuild these images:
- `orders` - DB slowdown, validation exception
- `shipping-processor` - DB slowdown
- `inventory` - DB slowdown
- `frontend` - DB slowdown
- `fulfillment` - cleaned up failure injection

---

## 6. Useful Commands

```bash
# Deploy fraud-detection-api
kubectl apply -f k8s/delay-service.yaml

# Redeploy all apps
kubectl apply -f k8s/fabrik-oa.yaml
kubectl apply -f k8s/fabrik-oa-2.yaml
kubectl apply -f k8s/fabrik-ot.yaml

# Recycle pods
kubectl rollout restart deployment -n fabrik-oa
kubectl rollout restart deployment -n fabrik-oa-2
kubectl rollout restart deployment -n fabrik-ot

# Check pod status
kubectl get pods -n fabrik-oa
kubectl get pods -n fabrik-oa-2
kubectl get pods -n fabrik-ot
kubectl get pods -n ext-services

# Close a Dynatrace problem via API
curl -X POST "https://abl46885.dev.dynatracelabs.com/api/v2/problems/P-XXXXX/close" \
  -H "Authorization: Api-Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Closing for demo reset"}'
```

---

*Last updated: 2026-01-20*

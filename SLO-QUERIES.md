# Dynatrace SLO DQL Queries for Fabrik Chaos Engineering

## 🎯 Fulfillment Kafka Consumer Success Rate

**Monitors:** QueryTimeoutException and KafkaException errors in fulfillment service
**Target:** 95% success rate
**Timeframe:** Last 5 minutes

### Option 1: Log-Based (Recommended)

```dql
fetch logs
| filter k8s.deployment.name == "fulfillment"
| filter matchesPhrase(content, "KafkaListener") or matchesPhrase(content, "consume")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or 
      matchesPhrase(content, "KafkaException")
    ), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

**Expected Results:**
- Normal operation: ~100%
- During chaos (FAILURE_RATE=30): ~70%
- After remediation: ~100%

---

### Option 2: Timeseries Pattern (Matches Dynatrace Example Format)

```dql
timeseries total=count(dt.entity.log, default:0), 
  by: { k8s.deployment.name }, 
  filter: { 
    k8s.deployment.name == "fulfillment" and (
      matchesPhrase(content, "KafkaListener") or 
      matchesPhrase(content, "consume")
    ) 
  }
| fieldsAdd errors=count(
    dt.entity.log, 
    filter: matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or 
      matchesPhrase(content, "KafkaException")
    )
  )
| fieldsAdd success=total[] - errors[]
| fieldsAdd sli=100 * (success[] / total[])
| fieldsKeep sli, k8s.deployment.name
```

---

## 🔍 Testing Queries (Use in Notebooks First)

### Test 1: Check if logs exist
```dql
fetch logs
| filter k8s.deployment.name == "fulfillment"
| summarize count()
```
Should return > 0

### Test 2: Check for errors
```dql
fetch logs
| filter k8s.deployment.name == "fulfillment"
| filter matchesPhrase(content, "ERROR")
| fields timestamp, content
| sort timestamp desc
| limit 10
```

### Test 3: Full success rate calculation (for testing in Notebooks)
```dql
fetch logs
| filter k8s.deployment.name == "fulfillment"
| filter matchesPhrase(content, "KafkaListener") or matchesPhrase(content, "consume")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or 
      matchesPhrase(content, "KafkaException")
    ), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd successRate = ((totalCount - errorCount) / totalCount) * 100
```
**Note:** For testing only - shows `successRate`. For SLO, use `sli` instead.

---

## 📊 Alternative SLO Queries

### Orders Service Success Rate

```dql
fetch logs
| filter k8s.deployment.name == "orders"
| filter matchesPhrase(content, "placeOrder") or matchesPhrase(content, "OrderService")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and 
    matchesPhrase(content, "QueryTimeoutException"), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

---

### Inventory Service Success Rate

```dql
fetch logs
| filter k8s.deployment.name == "inventory"
| filter matchesPhrase(content, "handleOrder") or matchesPhrase(content, "check inventory")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and 
    matchesPhrase(content, "QueryTimeoutException"), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

---

### Shipping Service Success Rate

```dql
fetch logs
| filter k8s.deployment.name == "shipping-receiver" or k8s.deployment.name == "shipping-processor"
| filter matchesPhrase(content, "shipOrder") or matchesPhrase(content, "receive")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or
      matchesPhrase(content, "Message processing failure")
    ), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

---

### Frontend HTTP Success Rate

```dql
fetch logs
| filter k8s.deployment.name == "frontend"
| filter matchesPhrase(content, "GET") or matchesPhrase(content, "POST")
| fieldsAdd isError = if(
    matchesPhrase(content, "500") or 
    matchesPhrase(content, "Internal Server Error"), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

---

## 🎯 Composite SLO (All Services)

```dql
fetch logs
| filter k8s.namespace.name in ["fabrik-oa", "fabrik-ot", "fabrik-oa-2"]
| filter k8s.deployment.name in ["fulfillment", "orders", "inventory", "shipping-receiver", "shipping-processor", "frontend"]
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or 
      matchesPhrase(content, "KafkaException") or
      matchesPhrase(content, "500")
    ), 
    1, 
    else: 0
  )
| summarize errorCount = sum(isError), totalCount = count()
| fieldsAdd sli = ((totalCount - errorCount) / totalCount) * 100
| fieldsKeep sli
```

---

## 📝 How to Use in Dynatrace UI

1. Go to **Platform** → **Site Reliability Guardian** → **SLOs**
2. Click **Create SLO**
3. Choose **Custom SLI**
4. Paste one of the queries above
5. Set:
   - **Timeframe:** Last 5 minutes
   - **Target:** 95.0
   - **Warning:** 97.0
6. Add tags: `chaos-engineering`, `auto-remediation`
7. Save

---

## 🧪 Trigger Chaos to Test

```bash
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual
```

Wait 2-3 minutes, then rerun the query. Success rate should drop to ~70%.

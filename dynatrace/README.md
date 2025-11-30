# Dynatrace Auto-Remediation Setup for Fabrik Chaos Engineering

This directory contains configuration for automated chaos detection and remediation using Dynatrace SLOs, Site Reliability Guardian, and Workflows.

## 🎯 Architecture

```
Fulfillment Kafka Consumer Failures (30% during chaos)
                    ↓
        SLO: Success Rate < 95%
                    ↓
    Site Reliability Guardian Validation FAILS
                    ↓
        Workflow Triggered Automatically
                    ↓
    ✓ Check chaos mode active (FAILURE_RATE env var)
    ✓ Verify recent deployment event (v2.0.0-green)
    ✓ Send Slack alert
    ✓ Execute: kubectl set env deployment/fulfillment FAILURE_RATE- ...
    ✓ Send SDLC rollback event (v1.0.0-blue)
    ✓ Wait 2 minutes for stabilization
    ✓ Re-validate SLO
    ✓ Send success/failure notification
                    ↓
          System Health Restored
```

## 📋 Problem Being Solved

**Symptoms During Chaos:**
```
2025-11-30T16:51:22.718Z ERROR 1 --- [ntainer#0-0-C-1] o.s.k.l.KafkaMessageListenerContainer    : Error handler threw an exception
org.springframework.kafka.KafkaException: Seek to current after exception
	at org.springframework.kafka.listener.SeekUtils.seekOrRecover(SeekUtils.java:208)
	at org.springframework.kafka.listener.DefaultErrorHandler.handleRemaining(DefaultErrorHandler.java:168)
	...

org.springframework.dao.QueryTimeoutException: PreparedStatementCallback; SQL [UPDATE orders ...]; Query timeout; 
nested exception is org.postgresql.util.PSQLException: ERROR: canceling statement due to user request
```

**Root Cause:**
- Fulfillment service Kafka consumer processing orders from `orders` topic
- Chaos injects `FAILURE_RATE=30` → 30% of messages throw QueryTimeoutException
- Results in Kafka message processing failures and retries
- Error rate spikes from ~0% to ~30%
- SLO breach: Success rate drops from 100% → ~70%

## 🚀 Quick Start

### Step 1: Create the SLO (Modern API Format)

**Recommended: Simple Log-Based SLO** ⭐ (No entity ID required!)

```bash
# Set your Dynatrace environment variables
export DT_API_URL='https://your-environment.live.dynatrace.com'
export DT_API_TOKEN='dt0c01.YOUR_TOKEN_HERE'  # Requires slo.write scope

# Create the SLO using the helper script
cd dynatrace/
./create-slo.sh slo-fulfillment-simple.json
```

**Why this approach?**
- ✅ Uses correct POST /api/v2/slo format with `customSli`
- ✅ No entity ID required - filters by Kubernetes deployment name
- ✅ Directly monitors log patterns for QueryTimeoutException and KafkaException
- ✅ Simple timeseries indicator format
- ✅ Fast detection (5-minute evaluation window)

**The indicator:**
```dql
timeseries successRate = (
  data record(
    avg = avg(
      if(
        matchesPhrase(content, "ERROR") and (
          matchesPhrase(content, "QueryTimeoutException") or 
          matchesPhrase(content, "KafkaException")
        ), 
        0, 
        else: 100
      )
    ), 
    by:{}, 
    filter: k8s.deployment.name == "fulfillment" and (
      matchesPhrase(content, "KafkaListener") or 
      matchesPhrase(content, "consume")
    ), 
    from: logs
  )
)
```

**Alternative Approaches:**

<details>
<summary>Option 2: Span-Based (Distributed Tracing)</summary>

Use `slo-fulfillment-span-failure-rate.json` for span-level monitoring:
```bash
./create-slo.sh slo-fulfillment-span-failure-rate.json
```
- Best for end-to-end transaction visibility
- Shows cascading failures across services
- No entity ID needed - uses `service.name`
</details>

<details>
<summary>Option 3: Via Dynatrace UI</summary>

1. Go to: **Platform** → **Site Reliability Guardian** → **SLOs**
2. Click **Create SLO**
3. Choose **Custom SLI**
4. Paste the indicator query (see SLO-API-GUIDE.md)
5. Set timeframe: **Last 5 minutes**
6. Set target: **95.0**, warning: **97.0**
7. Add tags: `chaos-engineering`, `auto-remediation`
8. Save

See **[SLO-API-GUIDE.md](SLO-API-GUIDE.md)** for complete UI instructions.
</details>

### Step 2: Create the Site Reliability Guardian

```bash
# Create guardian via UI (recommended) or API
# Settings > Cloud Automation > Site Reliability Guardian
# - Name: "Fulfillment Chaos Detection Guardian"
# - Objective: fulfillment-kafka-consumer-success-rate
# - Target: 95%
# - Evaluation Window: 5 minutes
# - Tags: chaos-guardian=fulfillment, auto-remediation=enabled
```

### Step 3: Set Up Kubernetes Integration

**Create Service Account with Remediation Permissions:**
```bash
# Create service account for Dynatrace automation
kubectl create serviceaccount dynatrace-automation -n fabrik-oa

# Create role with env var modification permissions
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dynatrace-chaos-remediation
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: dynatrace-chaos-remediation
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: dynatrace-chaos-remediation
subjects:
- kind: ServiceAccount
  name: dynatrace-automation
  namespace: fabrik-oa
EOF

# Get service account token
kubectl create token dynatrace-automation -n fabrik-oa --duration=87600h
```

**Configure in Dynatrace:**
1. Settings > Cloud and virtualization > Kubernetes
2. Add cluster connection with service account token
3. Verify connectivity

### Step 4: Create the Workflow

1. **Navigate to Workflows:**
   - Dynatrace UI > Automation > Workflows > Create workflow

2. **Configure Trigger:**
   - Type: Event
   - Event query: 
     ```
     event.type="guardian.validation.failed" AND 
     matchesPhrase(guardian.name, "Fulfillment Chaos Detection Guardian")
     ```

3. **Add Tasks** (in order):
   - Check chaos active (Kubernetes: Get env vars)
   - Get recent deployment (SRG: Run validation)
   - Send alert (Slack: Post message)
   - Disable chaos (3x Kubernetes: Run kubectl) - parallel for each namespace
   - Send SDLC event (HTTP: POST to events API)
   - Wait for stabilization (Sleep: 120s)
   - Revalidate SLO (SRG: Run validation)
   - Send success notification (Slack: Post message) - conditional
   - Send failure notification (Slack: Post message) - conditional

4. **Configure Slack Integration:**
   - Settings > Integration > Slack
   - Add workspace and authorize
   - Replace `C01234567` in workflow with real channel ID

5. **Test:**
   ```bash
   # Trigger chaos manually
   kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual
   
   # Watch for SLO breach in ~2-3 minutes
   # Workflow should trigger automatically
   # Check Slack for notifications
   ```

### Step 5: Alternative - Remediation Endpoint Approach

If you prefer a simpler webhook-based approach instead of Kubernetes actions:

**Add remediation endpoint to argo-cd pod:**
```bash
# Edit apps/argo-cd/remediate.sh
cat <<'EOF' > apps/argo-cd/remediate.sh
#!/bin/bash
echo "🚨 AUTO-REMEDIATION TRIGGERED"

# Remove chaos env vars
for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
    kubectl set env deployment/fulfillment FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n $ns
done

# Send SDLC event
source /app/simulate.sh
send_sdlc_event "finished" "v1.0.0-blue (auto-rollback)"

echo "✅ Remediation complete"
EOF

chmod +x apps/argo-cd/remediate.sh
```

**Simplify workflow to just:**
1. Check chaos active
2. Send alert
3. Call webhook: `kubectl exec -n default deploy/argo -- /app/remediate.sh`
4. Wait + revalidate
5. Send notification

## 📊 SLO Details

### Fulfillment Kafka Consumer Success Rate

**Target:** 95% success rate  
**Warning:** 97% success rate  
**Evaluation Window:** 5 minutes  
**Error Budget Burn Rate:** 10x (fast burn detection)

**DQL Query:**
```dql
fetch logs
| filter k8s.deployment.name == "fulfillment"
| filter matchesPhrase(content, "KafkaListener") or matchesPhrase(content, "consume")
| fieldsAdd isError = if(
    matchesPhrase(content, "ERROR") and (
      matchesPhrase(content, "QueryTimeoutException") or
      matchesPhrase(content, "KafkaException") or
      matchesPhrase(content, "KafkaMessageListenerContainer")
    ),
    1,
    else: 0
  )
| summarize {
    total = count(),
    errors = sum(isError)
  }
| fieldsAdd successRate = ((total - errors) / total) * 100
```

**What it measures:**
- Success rate of fulfillment service Kafka message processing from logs
- Detects QueryTimeoutException from database chaos
- Detects KafkaException from message processing failures
- Uses Kubernetes deployment labels (no entity ID needed)

**During normal operation:** ~100% success rate  
**During chaos (FAILURE_RATE=30):** ~70% success rate ❌ Breach!  
**Expected after remediation:** ~100% success rate ✅ Restored

## 🔍 Monitoring the Auto-Remediation

**Before Chaos:**
```bash
# Check SLO status (replace SLO_ID with actual ID from creation)
curl -X GET "${DT_API_URL}/api/v2/slo/{SLO_ID}" \
  -H "Authorization: Api-Token ${DT_API_TOKEN}" | jq .

# Or view in UI: Platform > Site Reliability Guardian > SLOs
# Should show: status=PASS, successRate=~100%
```

**During Chaos:**
```bash
# Watch for SLO breach
# After 5 minutes of chaos, should show: status=FAIL, sloValue=~70

# Check if workflow triggered
# Automation > Workflows > Executions > Look for "Fulfillment Chaos Auto-Remediation"

# Monitor pod restarts
kubectl get pods -n fabrik-oa -w | grep fulfillment
```

**After Remediation:**
```bash
# Verify chaos disabled
kubectl get deployment fulfillment -n fabrik-oa -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="FAILURE_RATE")].value}'
# Should return empty

# Check SLO recovery
# Should show: status=PASS, sloValue=~100 within 2-3 minutes
```

## 🎬 Demo Script

1. **Show baseline:** "Fulfillment service running smoothly at 100% success rate"
2. **Trigger chaos:** `kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual`
3. **Watch metrics degrade:** "Error rate spiking, response times increasing"
4. **SLO breach:** "Site Reliability Guardian detects SLO violation after 5 minutes"
5. **Auto-remediation triggers:** "Workflow automatically disables chaos injection"
6. **Show recovery:** "Success rate returns to 100% within 2 minutes"
7. **Audit trail:** "Complete observability of detection → remediation → validation"

## 🛠️ Troubleshooting

**SLO not detecting failures:**
- Check service entity exists: `entityName("fulfillment")`
- Verify metric has data: Query `builtin:service.requestCount.server` in Data Explorer
- Adjust filter to match your environment tags

**Workflow not triggering:**
- Check event query matches guardian name exactly
- Verify trigger is enabled
- Look for events: Settings > Business Events > Search for `guardian.validation.failed`

**Kubernetes actions failing:**
- Verify service account token is valid
- Check RBAC permissions with `kubectl auth can-i patch deployment --as=system:serviceaccount:fabrik-oa:dynatrace-automation`
- Review workflow execution logs for error details

**Remediation not working:**
- Verify pods actually restart: `kubectl get events -n fabrik-oa --sort-by='.lastTimestamp'`
- Check if env vars were removed: `kubectl describe deployment fulfillment -n fabrik-oa`
- Look for errors in fulfillment logs after remediation

## 📚 References

- [Dynatrace SLO Documentation](https://docs.dynatrace.com/docs/platform/davis-ai/cloud-automation/site-reliability-guardian/slo)
- [Site Reliability Guardian](https://docs.dynatrace.com/docs/platform/davis-ai/cloud-automation/site-reliability-guardian)
- [Dynatrace Workflows](https://docs.dynatrace.com/docs/platform/automation/workflows)
- [Kubernetes Actions](https://docs.dynatrace.com/docs/platform/automation/workflows/actions/kubernetes)

## 🔮 Future Enhancements

- [ ] Gradual remediation (reduce FAILURE_RATE incrementally)
- [ ] Multi-service SLO (orders + fulfillment + inventory)
- [ ] Circuit breaker pattern integration
- [ ] A/B testing with partial rollback
- [ ] Canary deployment with automatic promotion/rollback
- [ ] PagerDuty integration for manual approval gate
- [ ] Davis AI problem correlation before remediation

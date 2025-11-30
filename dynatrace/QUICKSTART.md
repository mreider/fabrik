# 🚀 Quick Start - Auto-Remediation in 20 Minutes

Get the complete auto-remediation loop running in 20 minutes.

---

## ⚡ Prerequisites (2 min)

```bash
# 1. Export Dynatrace credentials
export DT_API_URL='https://abc12345.live.dynatrace.com'
export DT_API_TOKEN='dt0c01.XXXXX'  # Needs: slo.write, automation.workflows.write

# 2. Verify kubectl access
kubectl cluster-info

# 3. Check current chaos state
kubectl get deployment fulfillment -n fabrik-oa \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="FAILURE_RATE")].value}'
# Should return empty (no chaos active)
```

---

## 📊 Step 1: Create SLO (3 min)

```bash
cd dynatrace/
./create-slo.sh slo-fulfillment-simple.json

# Expected output:
# ✅ SLO created successfully!
# SLO ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# View in Dynatrace: https://...
```

**Verify in UI:**
- Platform → Site Reliability Guardian → SLOs
- Should show "Fulfillment Kafka Consumer Success Rate (DQL)"
- Status: PASS, Success Rate: ~100%

---

## 🛡️ Step 2: Create Guardian (5 min)

**In Dynatrace UI:**

1. Go to: **Platform** → **Site Reliability Guardian** → **Create Guardian**

2. Basic Info:
   - Name: `Fulfillment Chaos Detection Guardian`
   - Description: `Detects chaos-induced Kafka consumer failures for auto-remediation`

3. Add Objective:
   - Click "+ Add objective"
   - Select: "Fulfillment Kafka Consumer Success Rate (DQL)"
   - Weight: 100
   - Target: 95.0
   - Warning: 97.0

4. Validation Settings:
   - Type: Simple
   - Condition: SLO not met
   - Evaluation window: 5 minutes

5. Tags:
   - Add: `chaos-guardian=fulfillment`
   - Add: `auto-remediation=enabled`

6. Click **Save**

---

## 🔐 Step 3: Setup Kubernetes Access (5 min)

```bash
cd ../scripts/
./setup-auto-remediation.sh

# Answer 'y' when prompted to create service account
# Expected output:
# ✅ Service account created
# Generate token with:
#   kubectl create token dynatrace-automation -n fabrik-oa --duration=87600h
```

**Get Token:**
```bash
TOKEN=$(kubectl create token dynatrace-automation -n fabrik-oa --duration=87600h)
echo $TOKEN
# Copy this token
```

**Add to Dynatrace:**
1. Go to: **Settings** → **Cloud and virtualization** → **Kubernetes**
2. Click **Connect new cluster**
3. Name: `fabrik-cluster`
4. API URL: Your cluster API (from `kubectl cluster-info`)
5. Token: Paste the token from above
6. Click **Connect**

---

## 🤖 Step 4: Create Workflow (5 min)

**Simplified approach - Use kubectl exec:**

1. Go to: **Automation** → **Workflows** → **Create workflow**
2. Name: `Fulfillment Chaos Auto-Remediation`

**Trigger:**
- Type: Event
- Event query:
  ```
  event.type="guardian.validation.failed" AND 
  matchesPhrase(guardian.name, "Fulfillment Chaos Detection Guardian")
  ```
- Enable trigger

**Tasks (add in order):**

### Task 1: Check Chaos Active
- Action: **Kubernetes: Run kubectl command**
- Command: 
  ```
  get deployment fulfillment -n fabrik-oa -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="FAILURE_RATE")].value}'
  ```
- Name: `check_chaos_active`

### Task 2: Remediate
- Action: **Kubernetes: Run kubectl command**
- Command:
  ```
  exec -n default -it deploy/argo -- /bin/bash -c "
  for ns in fabrik-oa fabrik-ot fabrik-oa-2; do 
    kubectl set env deployment/fulfillment FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n \$ns
  done"
  ```
- Name: `run_remediation`
- Condition: `{{ result('check_chaos_active') != '' }}`

### Task 3: Wait
- Action: **Utilities: Sleep**
- Duration: `120` (seconds)
- Name: `wait_for_recovery`

### Task 4: Validate
- Action: **Site Reliability Guardian: Run validation**
- Guardian: Select "Fulfillment Chaos Detection Guardian"
- Timeframe: `-3m`
- Name: `revalidate_slo`

**Save and enable workflow**

---

## ✅ Step 5: Test the Loop (5 min)

### Trigger Chaos:
```bash
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual
```

**Expected output:**
```
🔥 CHAOS MODE ON - Simulating problematic deployment v2.0.0-green
Setting up chaos environment variables...
Chaos simulation will run for 10 minutes...
```

### Watch the Auto-Remediation:

**Minute 0-5: Chaos Active**
- Check logs: `kubectl logs -n fabrik-oa deployment/fulfillment --tail=50`
- Should see ERROR logs with QueryTimeoutException

**Minute 5: SLO Breach**
- Open Dynatrace: Platform → Site Reliability Guardian → SLOs
- Success rate should drop to ~70%
- Status: FAIL

**Minute 5-7: Auto-Remediation**
- Go to: Automation → Workflows → Executions
- Should see "Fulfillment Chaos Auto-Remediation" running
- Watch tasks execute

**Minute 7-8: Recovery**
- Pods restart: `kubectl get pods -n fabrik-oa -w | grep fulfillment`
- SLO recovers to ~100%
- Status: PASS

### Verify Remediation:
```bash
# Check env vars removed
kubectl get deployment fulfillment -n fabrik-oa \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="FAILURE_RATE")].value}'
# Should return empty

# Check pod restarts
kubectl get pods -n fabrik-oa -l app=fulfillment
# AGE should be recent (< 5 minutes)
```

---

## 🎯 Success Criteria

✅ SLO created and showing 100% success rate  
✅ Guardian created with SLO objective  
✅ Kubernetes integration connected  
✅ Workflow created and enabled  
✅ Chaos triggers successfully  
✅ SLO breach detected after 5 minutes  
✅ Workflow executes automatically  
✅ Chaos disabled and pods restart  
✅ SLO recovers to 100%  
✅ Total MTTR: ~2 minutes  

---

## 🐛 Quick Troubleshooting

**SLO not detecting failures:**
```bash
# Check logs are ingested
kubectl logs -n fabrik-oa deployment/fulfillment --tail=100 | grep ERROR
# Should see QueryTimeoutException during chaos
```

**Workflow not triggering:**
```bash
# Check guardian events in Notebooks
fetch events
| filter event.type == "guardian.validation.failed"
| sort timestamp desc
| limit 5
```

**Kubernetes action failing:**
```bash
# Test RBAC
kubectl auth can-i patch deployment \
  --as=system:serviceaccount:fabrik-oa:dynatrace-automation \
  -n fabrik-oa
```

**Manual remediation:**
```bash
cd scripts/
./remediate.sh fulfillment "manual test"
```

---

## 📚 Next Steps

1. **Add Slack Integration** (optional)
   - Settings → Integration → Slack
   - Add notification tasks to workflow

2. **Extend to Other Services**
   - Create SLOs for orders, inventory, shipping
   - Add to same guardian

3. **Production Hardening**
   - Add approval gates
   - Implement gradual rollback
   - Set up PagerDuty integration

4. **Read Full Documentation**
   - `README.md` - Complete setup guide
   - `DQL-REFERENCE.md` - Query patterns
   - `ARCHITECTURE.md` - System design

---

## 🎬 Demo Commands

```bash
# Start chaos
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual

# Watch logs
kubectl logs -n fabrik-oa deployment/fulfillment -f | grep ERROR

# Check SLO (replace with your SLO ID)
curl -X GET "${DT_API_URL}/api/v2/slo/{SLO_ID}" \
  -H "Authorization: Api-Token ${DT_API_TOKEN}" | jq .

# Monitor pods
kubectl get pods -n fabrik-oa -w | grep fulfillment

# Manual cleanup if needed
./scripts/remediate.sh all
```

---

**Total Time: ~20 minutes**  
**Result: Fully automated chaos detection and remediation!**

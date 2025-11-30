# 📚 Dynatrace Auto-Remediation Documentation Index

Complete guide to implementing self-healing chaos engineering with Dynatrace.

---

## 🎯 Start Here

### **New to this project?**
→ Start with **[QUICKSTART.md](QUICKSTART.md)** (20 minutes)

### **Want to understand the architecture?**
→ Read **[ARCHITECTURE.md](ARCHITECTURE.md)** (5 minutes)

### **Need complete setup instructions?**
→ Follow **[README.md](README.md)** (30 minutes)

### **Looking for DQL query examples?**
→ Check **[DQL-REFERENCE.md](DQL-REFERENCE.md)** (reference)

### **Want a high-level overview?**
→ See **[SUMMARY.md](SUMMARY.md)** (10 minutes)

---

## 📖 Documentation Files

| File | Purpose | Time | Audience |
|------|---------|------|----------|
| **QUICKSTART.md** | Get auto-remediation running fast | 20 min | Implementers |
| **README.md** | Complete setup with all options | 30 min | Engineers |
| **ARCHITECTURE.md** | System design and flow diagrams | 5 min | Architects |
| **DQL-REFERENCE.md** | Query patterns and debugging | - | Developers |
| **SUMMARY.md** | Executive overview and demo script | 10 min | Demo presenters |

---

## 🗂️ Configuration Files

### SLO Definitions (Modern DQL-Based)
- **`slo-fulfillment-simple.json`** ⭐ **USE THIS**
  - Log-based, no entity ID required
  - Detects QueryTimeoutException and KafkaException
  - 5-minute evaluation window
  
- `slo-fulfillment-kafka-success-rate.json`
  - Service metrics approach (requires entity ID)
  
- `slo-fulfillment-kafka-success-rate-alternative.json`
  - Alternative log-based approach
  
- `slo-fulfillment-span-failure-rate.json`
  - Distributed tracing approach

### Guardian & Workflow
- **`guardian-fulfillment-chaos-detection.json`**
  - Site Reliability Guardian configuration
  - Triggers workflow on SLO breach
  
- **`workflow-fulfillment-auto-remediation.json`**
  - Complete workflow template
  - 11-step remediation process

---

## 🛠️ Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| **`create-slo.sh`** | Create SLO via API | `./create-slo.sh slo-fulfillment-simple.json` |
| **`../scripts/remediate.sh`** | Manual remediation | `./remediate.sh fulfillment "reason"` |
| **`../scripts/setup-auto-remediation.sh`** | Prerequisites check | `./setup-auto-remediation.sh` |

---

## 🚀 Quick Navigation

### I want to...

**...create the SLO**
```bash
./create-slo.sh slo-fulfillment-simple.json
```
→ See [README.md - Step 1](README.md#step-1-create-the-slo-modern-dql-approach)

**...understand the DQL query**
→ See [DQL-REFERENCE.md - Recommended Query](DQL-REFERENCE.md#-recommended-slo-query-log-based)

**...set up the Guardian**
→ See [README.md - Step 2](README.md#step-2-create-the-site-reliability-guardian)

**...configure Kubernetes access**
```bash
./setup-auto-remediation.sh
```
→ See [README.md - Step 3](README.md#step-3-set-up-kubernetes-integration)

**...create the Workflow**
→ See [README.md - Step 4](README.md#step-4-create-the-workflow)

**...test the system**
```bash
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual
```
→ See [QUICKSTART.md - Step 5](QUICKSTART.md#-step-5-test-the-loop-5-min)

**...troubleshoot issues**
→ See [README.md - Troubleshooting](README.md#-troubleshooting)

**...customize for my environment**
→ See [DQL-REFERENCE.md - Alternative Patterns](DQL-REFERENCE.md#-alternative-query-patterns)

**...demo this to stakeholders**
→ See [SUMMARY.md - Demo Script](SUMMARY.md#-demo-script)

---

## 🎓 Learning Path

### Beginner
1. Read [SUMMARY.md](SUMMARY.md) - Understand the problem
2. Follow [QUICKSTART.md](QUICKSTART.md) - Get it running
3. Test chaos: Trigger and watch auto-remediation

### Intermediate
1. Read [ARCHITECTURE.md](ARCHITECTURE.md) - Understand the design
2. Read [README.md](README.md) - Learn all configuration options
3. Customize SLO queries for your needs

### Advanced
1. Study [DQL-REFERENCE.md](DQL-REFERENCE.md) - Master queries
2. Create SLOs for other services (orders, inventory)
3. Implement gradual remediation strategies
4. Add multi-service composite SLOs

---

## 📊 File Dependencies

```
QUICKSTART.md (start here)
    ↓
create-slo.sh → slo-fulfillment-simple.json
    ↓
guardian-fulfillment-chaos-detection.json (via UI)
    ↓
setup-auto-remediation.sh (creates K8s resources)
    ↓
workflow-fulfillment-auto-remediation.json (via UI)
    ↓
remediate.sh (called by workflow)
```

**For deep dives:**
- README.md (comprehensive guide)
- DQL-REFERENCE.md (query details)
- ARCHITECTURE.md (system design)
- SUMMARY.md (executive overview)

---

## 🔍 Quick Reference

### Environment Variables
```bash
export DT_API_URL='https://abc12345.live.dynatrace.com'
export DT_API_TOKEN='dt0c01.XXX'  # Needs: slo.write, automation.workflows.write
```

### Key Commands
```bash
# Create SLO
./create-slo.sh slo-fulfillment-simple.json

# Setup prerequisites
../scripts/setup-auto-remediation.sh

# Trigger chaos
kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual

# Manual remediation
../scripts/remediate.sh fulfillment "test"

# Check chaos state
kubectl get deployment fulfillment -n fabrik-oa \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="FAILURE_RATE")].value}'
```

### Key URLs
- SLOs: Platform → Site Reliability Guardian → SLOs
- Guardians: Platform → Site Reliability Guardian → Guardians
- Workflows: Automation → Workflows
- Events: Settings → Business Events

---

## 🆘 Getting Help

**Issue: SLO not detecting failures**
→ [README.md - Troubleshooting - SLO not detecting failures](README.md#troubleshooting)

**Issue: Workflow not triggering**
→ [README.md - Troubleshooting - Workflow not triggering](README.md#troubleshooting)

**Issue: Kubernetes actions failing**
→ [README.md - Troubleshooting - Kubernetes actions failing](README.md#troubleshooting)

**Issue: Want to understand DQL queries better**
→ [DQL-REFERENCE.md - Debugging Queries](DQL-REFERENCE.md#-debugging-queries)

---

## 📈 Success Metrics

After completing setup, you should see:

✅ SLO showing 100% success rate at baseline  
✅ SLO dropping to ~70% during chaos (FAILURE_RATE=30)  
✅ Guardian detecting breach after 5 minutes  
✅ Workflow executing automatically  
✅ Chaos disabled within 2 minutes  
✅ SLO recovering to 100% within 3 minutes  
✅ Complete audit trail in Dynatrace  

**MTTR improvement: 10 minutes (manual) → 2 minutes (auto) = 80% reduction**

---

## 🔮 Next Steps

After mastering the basics:

1. **Extend to other services**
   - Create SLOs for orders, inventory, shipping
   - Add to composite guardian

2. **Add notifications**
   - Slack integration for alerts
   - PagerDuty for escalations

3. **Production hardening**
   - Add approval gates
   - Implement gradual rollback
   - Set up cost tracking

4. **Advanced patterns**
   - Canary deployments with auto-rollback
   - A/B testing with SLO validation
   - Circuit breaker integration

---

## 📚 External Resources

- [Dynatrace DQL Documentation](https://docs.dynatrace.com/docs/platform/grail/dynatrace-query-language)
- [Site Reliability Guardian](https://docs.dynatrace.com/docs/platform/davis-ai/cloud-automation/site-reliability-guardian)
- [Dynatrace Workflows](https://docs.dynatrace.com/docs/platform/automation/workflows)
- [Kubernetes Actions](https://docs.dynatrace.com/docs/platform/automation/workflows/actions/kubernetes)

---

**Last Updated:** November 30, 2025  
**Version:** 1.0 (Modern DQL-based)  
**Status:** Production Ready

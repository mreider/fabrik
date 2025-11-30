```mermaid
flowchart TB
    subgraph "Fabrik Microservices"
        FC[Fulfillment Service<br/>Kafka Consumer]
        K[Kafka: orders topic]
        DB[(PostgreSQL)]
        
        K -->|30% failures| FC
        FC -->|QueryTimeoutException| DB
    end
    
    subgraph "Dynatrace Platform"
        subgraph "Observability Layer"
            LOGS[Grail Logs<br/>KafkaException, QueryTimeoutException]
            SPANS[Distributed Traces<br/>Span Status: ERROR]
            METRICS[Service Metrics<br/>HTTP 5xx Errors]
        end
        
        subgraph "SLO & Guardian"
            DQL["DQL Query (5-min window)<br/>fetch logs | filter k8s.deployment.name == 'fulfillment'<br/>| fieldsAdd isError = matchesPhrase(content, 'ERROR')"]
            SLO["SLO: Success Rate<br/>Target: 95%<br/>Warning: 97%"]
            SRG["Site Reliability Guardian<br/>Evaluation: Every 5 minutes<br/>Fast Burn Rate: 10x"]
            
            DQL -->|Calculates| SLO
            SLO -->|Validates| SRG
        end
        
        subgraph "Automation Layer"
            WF["Dynatrace Workflow<br/>Fulfillment Chaos Auto-Remediation"]
            K8S["Kubernetes Integration<br/>Service Account: dynatrace-automation"]
            SLACK[Slack Integration<br/>Notifications]
        end
    end
    
    subgraph "Kubernetes Cluster"
        DEPLOY["Deployment: fulfillment<br/>FAILURE_RATE=30<br/>SLOWDOWN_RATE=35"]
        PODS["Pods Restarting<br/>Env Vars Removed"]
        NS["Namespaces:<br/>fabrik-oa, fabrik-ot, fabrik-oa-2"]
        
        DEPLOY --> PODS
        PODS --> NS
    end
    
    subgraph "Chaos Injection"
        ARGO[ArgoCD Simulator<br/>simulate.sh]
        SDLC1[SDLC Event: v2.0.0-green<br/>status: started]
        SDLC2[SDLC Event: v1.0.0-blue<br/>status: finished<br/>remediation.type: auto-rollback]
    end
    
    %% Flow connections
    FC -->|Logs| LOGS
    FC -->|Traces| SPANS
    FC -->|Metrics| METRICS
    
    SRG -->|"Breach: successRate < 95%"| WF
    WF -->|"1. Check chaos active"| K8S
    WF -->|"2. Send alert"| SLACK
    WF -->|"3. Remove env vars"| DEPLOY
    WF -->|"4. Send SDLC event"| SDLC2
    WF -->|"5. Re-validate"| SRG
    WF -->|"6. Confirm recovery"| SLACK
    
    ARGO -->|"Sets env vars"| DEPLOY
    ARGO -->|"Sends event"| SDLC1
    SDLC1 -.->|"Correlates with"| SRG
    
    %% Styling
    classDef chaos fill:#ffebee,stroke:#d32f2f,stroke-width:2px
    classDef observability fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef automation fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef k8s fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    classDef success fill:#c8e6c9,stroke:#4caf50,stroke-width:3px
    
    class FC,K,DB chaos
    class LOGS,SPANS,METRICS,DQL,SLO,SRG observability
    class WF,K8S,SLACK automation
    class DEPLOY,PODS,NS k8s
    class SDLC2 success
```

# Auto-Remediation Architecture

## 🔄 Complete Flow

### Phase 1: Chaos Injection (T+0)
1. ArgoCD simulator sets `FAILURE_RATE=30` on fulfillment deployment
2. Sends SDLC event: "v2.0.0-green deployment started"
3. Pods restart with chaos environment variables
4. 30% of Kafka messages throw `QueryTimeoutException`

### Phase 2: Observability (T+0 to T+5min)
1. Grail ingests error logs from fulfillment pods
2. Distributed traces show ERROR spans
3. Service metrics capture 5xx responses
4. DQL query runs every 5 minutes to calculate success rate

### Phase 3: Detection (T+5min)
1. DQL query result: `successRate = 70%` (below 95% target)
2. SLO status changes: PASS → FAIL
3. Site Reliability Guardian validation fails
4. Guardian emits `guardian.validation.failed` event

### Phase 4: Auto-Remediation (T+5min to T+7min)
1. Workflow triggers on guardian event
2. Step 1: Check if `FAILURE_RATE` env var exists (chaos active)
3. Step 2: Send Slack alert: "SLO breach detected, remediating..."
4. Step 3: Execute `kubectl set env deployment/fulfillment FAILURE_RATE-` (3x namespaces)
5. Step 4: Send SDLC event: "v1.0.0-blue deployment finished (auto-rollback)"
6. Step 5: Wait 120 seconds for pods to restart
7. Step 6: Re-run guardian validation

### Phase 5: Recovery (T+7min to T+8min)
1. Pods restart without chaos env vars
2. Success rate returns to ~100%
3. SLO status: FAIL → PASS
4. Workflow sends Slack notification: "Auto-remediation complete"

## 📊 Key Metrics

| Metric | Before Chaos | During Chaos | After Remediation |
|--------|-------------|--------------|-------------------|
| Success Rate | 100% | 70% | 100% |
| Error Rate | 0% | 30% | 0% |
| SLO Status | PASS | FAIL | PASS |
| Response Time | 200ms | 800ms | 200ms |
| MTTR | - | 10min (manual) | 2min (auto) |

## 🎯 Why This Works

1. **No Entity IDs Required** - DQL uses Kubernetes labels
2. **Fast Detection** - 5-minute SLO evaluation window
3. **Automated Action** - Workflow directly manipulates K8s
4. **Full Observability** - Logs, traces, metrics all correlated
5. **Deployment Correlation** - SDLC events link chaos to deployment
6. **Self-Healing** - Closed-loop remediation without human intervention

## 🚀 Demo Value

**Traditional Monitoring:**
- Alerts fire → human investigates → identifies chaos → manually disables → 10+ minutes

**With Auto-Remediation:**
- SLO breach → guardian validates → workflow remediates → 2 minutes

**Savings: 80% reduction in MTTR**

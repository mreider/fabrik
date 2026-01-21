#!/bin/bash

DT_API_URL="${DT_API_URL}"
DT_API_TOKEN="${DT_API_TOKEN}"

# Function to send SDLC event
send_sdlc_event() {
    local status=$1
    local version=$2
    local name="Deploy Services ${version}"
    
    # Current time in nanoseconds and unique execution ID
    local timestamp=$(date +%s)000000000
    local execution_id="${timestamp}_$(shuf -i 10000-99999 -n 1)"
    
    echo "Sending deployment ${status} event for ${version}..."

    payload=$(cat <<EOF
{
  "eventType": "CUSTOM_INFO",
  "title": "ArgoCD Deployment ${status} for ${version}",
  "timestamp": ${timestamp},
  "properties": {
    "event.kind": "SDLC_EVENT",
    "event.category": "task",
    "event.type": "deployment",
    "event.status": "${status}",
    "event.provider": "argocd",
    "cicd.deployment.name": "${name}",
    "cicd.deployment.status": "succeeded",
    "cicd.deployment.release_stage": "production",
    "service.version": "${version}",
    "task.outcome": "succeeded",
    "argocd.app.project.name": "fabrik",
    "argocd.app.name": "fabrik",
    "argocd.app.owner": "fabrik team",
    "argocd.app.stage": "production",
    "argocd.app.version": "${version}",
    "event.timestamp": "${timestamp}",
    "execution.id": "${execution_id}"
  }
}
EOF
)

    curl -X POST "${DT_API_URL}/v2/events/ingest" \
         -H "Authorization: Api-Token ${DT_API_TOKEN}" \
         -H "Content-Type: application/json; charset=utf-8" \
         -d "$payload"
         
    echo ""
}

run_simulation() {
    echo "Starting Fabrik Chaos Engineering Simulation..."
    echo "This simulates correlated failures across the microservices architecture"
    echo "to demonstrate Dynatrace Davis AI anomaly detection and root cause analysis."

    # Generate unique version with realistic commit hash
    local bad_hash=$(openssl rand -hex 6)
    local good_hash=$(openssl rand -hex 6)
    local bad_version="v2.0.0-green-${bad_hash}"
    local good_version="v1.0.0-blue-${good_hash}"

    # 1. Send Deployment Started
    send_sdlc_event "started" "$bad_version"

    # 2. Correlated Failure Episode (10 minutes)
    # Simulates a problematic deployment with cascading failures:
    # - Database query timeouts (orders, fulfillment, inventory, shipping)
    # - HTTP 500 errors (frontend)
    # - Message processing failures (kafka consumers)
    # - gRPC communication failures (shipping processor)
    echo "Starting correlated failure simulation (10 minutes)..."
    echo "Injecting failures: DB timeouts, HTTP 500s, messaging failures, gRPC errors"

    echo "🔥 CHAOS MODE ON - Simulating problematic deployment $bad_version"

    # Check if chaos mode is already active
    chaos_active=$(kubectl get deployment orders -n fabrik-oa -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='FAILURE_RATE')].value}" 2>/dev/null || echo "")

    if [[ -n "$chaos_active" ]]; then
        echo "ℹ️  Chaos mode already active (FAILURE_RATE=$chaos_active), skipping environment setup"
    else
        echo "🔧 Setting up chaos environment variables..."
        for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
             echo "  Configuring chaos in namespace: $ns"

             # Core services with high failure rates (simulate DB connection pool exhaustion)
             kubectl set env deployment/orders FAILURE_RATE=30 -n $ns >/dev/null 2>&1
             kubectl set env deployment/fulfillment FAILURE_RATE=30 -n $ns >/dev/null 2>&1

             # Inventory service (inventory lookup timeouts + message processing slowdowns)
             kubectl set env deployment/inventory FAILURE_RATE=25 MSG_SLOWDOWN_RATE=50 MSG_SLOWDOWN_DELAY=1500 -n $ns >/dev/null 2>&1

             # Shipping services (messaging and gRPC failures + message processing slowdowns)
             kubectl set env deployment/shipping-receiver FAILURE_RATE=20 MSG_SLOWDOWN_RATE=45 MSG_SLOWDOWN_DELAY=1200 -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-processor FAILURE_RATE=20 -n $ns >/dev/null 2>&1

             # Frontend (HTTP 500s and slow responses)
             kubectl set env deployment/frontend FAILURE_RATE=15 -n $ns >/dev/null 2>&1

             # Independent slowdown injection (affects successful requests)
             kubectl set env deployment/orders SLOWDOWN_RATE=40 SLOWDOWN_DELAY=2000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/fulfillment SLOWDOWN_RATE=35 SLOWDOWN_DELAY=1500 -n $ns >/dev/null 2>&1
             kubectl set env deployment/inventory SLOWDOWN_RATE=30 SLOWDOWN_DELAY=3000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-receiver SLOWDOWN_RATE=25 SLOWDOWN_DELAY=1000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-processor SLOWDOWN_RATE=20 SLOWDOWN_DELAY=2500 -n $ns >/dev/null 2>&1
             kubectl set env deployment/frontend SLOWDOWN_RATE=35 SLOWDOWN_DELAY=1800 -n $ns >/dev/null 2>&1
        done
        echo "✅ Chaos environment variables configured"
    fi

    echo "Chaos simulation will run for 10 minutes..."
    echo "Expected symptoms:"
    echo "  • Increased response times across all services (independent slowdowns)"
    echo "  • Database query timeout exceptions (failure injection)"
    echo "  • HTTP 500 error rate spikes (failure injection)"
    echo "  • Message processing failures (failure injection)"
    echo "  • Message deserialization and validation slowdowns (msg processing injection)"
    echo "  • Consumer group rebalancing delays (msg processing injection)"
    echo "  • Dead letter queue processing overhead (msg processing injection)"
    echo "  • gRPC communication errors (failure injection)"
    echo "  • End-to-end transaction failures (combined effect)"
    echo "  • Response time degradation on successful requests (slowdown injection)"
    echo "  • Mixed performance patterns: slow successes + fast failures + slow message processing"

    # Wait 10 minutes for chaos to show impact
    sleep 600

    echo "✅ CHAOS MODE OFF - Rolling back to stable version $good_version"

    # Check if cleanup is needed
    chaos_active=$(kubectl get deployment orders -n fabrik-oa -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='FAILURE_RATE')].value}" 2>/dev/null || echo "")

    if [[ -z "$chaos_active" ]]; then
        echo "ℹ️  Chaos mode already disabled, skipping cleanup"
    else
        echo "🔧 Cleaning up chaos environment variables..."
        for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
             echo "  Cleaning chaos in namespace: $ns"
             kubectl set env deployment/orders FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/fulfillment FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/inventory FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- MSG_SLOWDOWN_RATE- MSG_SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-receiver FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- MSG_SLOWDOWN_RATE- MSG_SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-processor FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/frontend FAILURE_RATE- SLOWDOWN_RATE- SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
        done
        echo "✅ Chaos environment variables cleaned up"
    fi

    # 3. Send Deployment Finished (Rollback to Good)
    send_sdlc_event "finished" "$good_version"

    echo "Rollback complete - System should return to baseline performance."
    echo "Davis AI should detect the anomaly period and correlate it with the deployment event."
    echo "Bad deployment: $bad_version → Good deployment: $good_version"
}

if [ "$1" == "manual" ]; then
    run_simulation
    exit 0
fi

# Loop forever
while true; do
    # Sleep for random time between 0 and 2 hours (0 to 7200 seconds)
    sleep_time=$((RANDOM % 7200))
    echo "Sleeping for ${sleep_time} seconds ($(($sleep_time / 60)) minutes)..."
    sleep $sleep_time

    run_simulation
done

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
    echo "This simulates DB-originated failures for proper Davis AI root cause detection."
    echo ""
    echo "Mechanism: Heavy PostgreSQL queries that exceed JDBC timeout"
    echo "  - DB_SLOWDOWN_RATE: Percentage of requests that get slow query"
    echo "  - DB_SLOWDOWN_DELAY: Target query duration (ms) - must exceed timeout to cause failure"
    echo "  - DB_QUERY_TIMEOUT_MS: JDBC timeout (ms) - queries exceeding this will fail"
    echo ""

    # Generate unique version with realistic commit hash
    local bad_hash=$(openssl rand -hex 6)
    local good_hash=$(openssl rand -hex 6)
    local bad_version="v2.0.0-green-${bad_hash}"
    local good_version="v1.0.0-blue-${good_hash}"

    # 1. Send Deployment Started
    send_sdlc_event "started" "$bad_version"

    echo "Starting DB-based chaos simulation (10 minutes)..."
    echo "Injecting: Database query timeouts that Davis will root-cause to PostgreSQL"

    echo "🔥 CHAOS MODE ON - Simulating problematic deployment $bad_version"

    # Check if chaos mode is already active
    chaos_active=$(kubectl get deployment orders -n fabrik-oa -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='DB_SLOWDOWN_RATE')].value}" 2>/dev/null || echo "")

    if [[ -n "$chaos_active" ]]; then
        echo "ℹ️  Chaos mode already active (DB_SLOWDOWN_RATE=$chaos_active), skipping environment setup"
    else
        echo "🔧 Setting up DB chaos environment variables..."
        for ns in fabrik-oa fabrik-ot; do
             echo "  Configuring DB chaos in namespace: $ns"

             # Set query timeout to 3 seconds - queries taking longer will fail
             # This is set via application.properties default, but can be overridden
             kubectl set env deployment/orders DB_QUERY_TIMEOUT_MS=3000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/fulfillment DB_QUERY_TIMEOUT_MS=3000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/inventory DB_QUERY_TIMEOUT_MS=3000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-processor DB_QUERY_TIMEOUT_MS=3000 -n $ns >/dev/null 2>&1
             kubectl set env deployment/frontend DB_QUERY_TIMEOUT_MS=3000 -n $ns >/dev/null 2>&1

             # Orders service: 30% of requests get 5-second DB query (will timeout at 3s)
             # This is the PRIMARY source of failures - Davis will root-cause to Database
             kubectl set env deployment/orders DB_SLOWDOWN_RATE=30 DB_SLOWDOWN_DELAY=5000 -n $ns >/dev/null 2>&1

             # Fulfillment service: 25% of requests get 4-second DB query
             kubectl set env deployment/fulfillment DB_SLOWDOWN_RATE=25 DB_SLOWDOWN_DELAY=4000 -n $ns >/dev/null 2>&1

             # Inventory service: 20% of requests get 5-second DB query + message slowdowns
             kubectl set env deployment/inventory DB_SLOWDOWN_RATE=20 DB_SLOWDOWN_DELAY=5000 MSG_SLOWDOWN_RATE=30 MSG_SLOWDOWN_DELAY=1000 -n $ns >/dev/null 2>&1

             # Shipping processor: 20% of requests get 4-second DB query
             kubectl set env deployment/shipping-processor DB_SLOWDOWN_RATE=20 DB_SLOWDOWN_DELAY=4000 -n $ns >/dev/null 2>&1

             # Shipping receiver: Message slowdowns only (no DB access)
             # Failures propagate from shipping-processor
             kubectl set env deployment/shipping-receiver MSG_SLOWDOWN_RATE=25 MSG_SLOWDOWN_DELAY=800 -n $ns >/dev/null 2>&1

             # Frontend: Light DB slowdown (shows impact, but root cause is downstream)
             kubectl set env deployment/frontend DB_SLOWDOWN_RATE=10 DB_SLOWDOWN_DELAY=4000 -n $ns >/dev/null 2>&1
        done
        echo "✅ DB chaos environment variables configured"
    fi

    echo ""
    echo "Chaos simulation will run for 10 minutes..."
    echo "Expected Davis AI detection:"
    echo "  • Root cause: PostgreSQL database query timeouts"
    echo "  • Affected services: orders → frontend (propagated failures)"
    echo "  • Error type: QueryTimeoutException / JDBC timeout"
    echo "  • Visual resolution path: Database → Service → HTTP endpoint"
    echo ""
    echo "Expected symptoms:"
    echo "  • Database query timeout exceptions (traceable to PostgreSQL)"
    echo "  • HTTP 500 errors propagating from backend to frontend"
    echo "  • Response time degradation on successful requests"
    echo "  • Message processing slowdowns in Kafka consumers"

    # Wait 10 minutes for chaos to show impact
    sleep 600

    echo "✅ CHAOS MODE OFF - Rolling back to stable version $good_version"

    # Check if cleanup is needed
    chaos_active=$(kubectl get deployment orders -n fabrik-oa -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='DB_SLOWDOWN_RATE')].value}" 2>/dev/null || echo "")

    if [[ -z "$chaos_active" ]]; then
        echo "ℹ️  Chaos mode already disabled, skipping cleanup"
    else
        echo "🔧 Cleaning up chaos environment variables..."
        for ns in fabrik-oa fabrik-ot; do
             echo "  Cleaning chaos in namespace: $ns"
             kubectl set env deployment/orders DB_SLOWDOWN_RATE- DB_SLOWDOWN_DELAY- DB_QUERY_TIMEOUT_MS- -n $ns >/dev/null 2>&1
             kubectl set env deployment/fulfillment DB_SLOWDOWN_RATE- DB_SLOWDOWN_DELAY- DB_QUERY_TIMEOUT_MS- -n $ns >/dev/null 2>&1
             kubectl set env deployment/inventory DB_SLOWDOWN_RATE- DB_SLOWDOWN_DELAY- DB_QUERY_TIMEOUT_MS- MSG_SLOWDOWN_RATE- MSG_SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-processor DB_SLOWDOWN_RATE- DB_SLOWDOWN_DELAY- DB_QUERY_TIMEOUT_MS- -n $ns >/dev/null 2>&1
             kubectl set env deployment/shipping-receiver MSG_SLOWDOWN_RATE- MSG_SLOWDOWN_DELAY- -n $ns >/dev/null 2>&1
             kubectl set env deployment/frontend DB_SLOWDOWN_RATE- DB_SLOWDOWN_DELAY- DB_QUERY_TIMEOUT_MS- -n $ns >/dev/null 2>&1
        done
        echo "✅ Chaos environment variables cleaned up"
    fi

    # 3. Send Deployment Finished (Rollback to Good)
    send_sdlc_event "finished" "$good_version"

    echo "Rollback complete - System should return to baseline performance."
    echo "Davis AI should detect: Database as root cause → Service failures → HTTP errors"
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

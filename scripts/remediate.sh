#!/bin/bash
#
# Remediation script for Fabrik chaos auto-remediation
# Can be called by Dynatrace Workflow or manually for testing
#
# Usage:
#   ./remediate.sh [service-name] [reason]
#
# Examples:
#   ./remediate.sh fulfillment "SLO breach detected"
#   ./remediate.sh all "manual intervention"
#

set -e

SERVICE=${1:-"all"}
REASON=${2:-"auto-remediation triggered"}

DT_API_URL="${DT_API_URL:-}"
DT_API_TOKEN="${DT_API_TOKEN:-}"

echo "======================================"
echo "🚨 FABRIK AUTO-REMEDIATION"
echo "======================================"
echo "Service: ${SERVICE}"
echo "Reason: ${REASON}"
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "======================================"

# Function to send SDLC event
send_sdlc_event() {
    local status=$1
    local version=$2
    
    if [[ -z "$DT_API_URL" ]] || [[ -z "$DT_API_TOKEN" ]]; then
        echo "⚠️  Skipping SDLC event (DT_API_URL or DT_API_TOKEN not set)"
        return
    fi
    
    local timestamp=$(date +%s)000000000
    local execution_id="${timestamp}_$(shuf -i 10000-99999 -n 1 2>/dev/null || echo $RANDOM)"
    
    echo "📤 Sending SDLC event: ${status} - ${version}"

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
    "cicd.deployment.name": "Deploy Services ${version}",
    "cicd.deployment.status": "succeeded",
    "cicd.deployment.release_stage": "production",
    "service.version": "${version}",
    "task.outcome": "succeeded",
    "remediation.type": "auto-rollback",
    "remediation.trigger": "site-reliability-guardian",
    "remediation.service": "${SERVICE}",
    "remediation.reason": "${REASON}"
  }
}
EOF
)

    curl -X POST "${DT_API_URL}/api/v2/events/ingest" \
         -H "Authorization: Api-Token ${DT_API_TOKEN}" \
         -H "Content-Type: application/json; charset=utf-8" \
         -d "$payload" \
         --silent --show-error
         
    echo ""
}

# Function to disable chaos for a service
disable_chaos_for_service() {
    local service_name=$1
    local namespaces=("fabrik-oa" "fabrik-ot" "fabrik-oa-2")
    
    echo ""
    echo "🔧 Disabling chaos for service: ${service_name}"
    
    for ns in "${namespaces[@]}"; do
        # Check if namespace exists
        if ! kubectl get namespace "$ns" &>/dev/null; then
            echo "  ⚠️  Namespace ${ns} not found, skipping"
            continue
        fi
        
        # Check if deployment exists
        if ! kubectl get deployment "${service_name}" -n "$ns" &>/dev/null; then
            echo "  ⚠️  Deployment ${service_name} not found in ${ns}, skipping"
            continue
        fi
        
        # Check if chaos is active
        failure_rate=$(kubectl get deployment "${service_name}" -n "$ns" -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='FAILURE_RATE')].value}" 2>/dev/null || echo "")
        
        if [[ -z "$failure_rate" ]]; then
            echo "  ℹ️  ${ns}/${service_name} - No chaos active, skipping"
            continue
        fi
        
        echo "  🔥 ${ns}/${service_name} - Chaos active (FAILURE_RATE=${failure_rate}), disabling..."
        
        # Remove all chaos environment variables
        kubectl set env deployment/"${service_name}" \
            FAILURE_RATE- \
            SLOWDOWN_RATE- \
            SLOWDOWN_DELAY- \
            MSG_SLOWDOWN_RATE- \
            MSG_SLOWDOWN_DELAY- \
            -n "$ns" \
            --overwrite \
            2>&1 | sed 's/^/    /'
        
        echo "  ✅ ${ns}/${service_name} - Chaos disabled"
    done
}

# Main remediation logic
case "$SERVICE" in
    "fulfillment"|"orders"|"inventory"|"shipping-receiver"|"shipping-processor"|"frontend")
        disable_chaos_for_service "$SERVICE"
        ;;
    "all")
        echo "🔥 Disabling chaos for ALL services"
        disable_chaos_for_service "fulfillment"
        disable_chaos_for_service "orders"
        disable_chaos_for_service "inventory"
        disable_chaos_for_service "shipping-receiver"
        disable_chaos_for_service "shipping-processor"
        disable_chaos_for_service "frontend"
        ;;
    *)
        echo "❌ Unknown service: ${SERVICE}"
        echo "Valid options: fulfillment, orders, inventory, shipping-receiver, shipping-processor, frontend, all"
        exit 1
        ;;
esac

# Send SDLC rollback event with unique version
local rollback_hash=$(openssl rand -hex 6 2>/dev/null || echo "$(date +%s | md5sum | cut -c1-12)")
send_sdlc_event "finished" "v1.0.0-blue-${rollback_hash} (auto-rollback)"

echo ""
echo "======================================"
echo "✅ REMEDIATION COMPLETE"
echo "======================================"
echo "Next steps:"
echo "  1. Wait 2-3 minutes for pods to restart"
echo "  2. Verify SLO recovery: kubectl get pods -n fabrik-oa"
echo "  3. Check metrics in Dynatrace"
echo "======================================"

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
    echo "Starting deployment simulation..."
    
    # 1. Send Deployment Started
    send_sdlc_event "started" "v2.0.0-green"
    
    # 2. Episodic Failure (10 minutes)
    # We enable FAILURE_RATE=30 for 10 minutes.
    # This causes ~30% failure during this "episode".
    echo "Starting episodic failure (10 minutes)..."
    
    echo "Fault ON"
    for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
         kubectl set env deployment/orders FAILURE_RATE=30 -n $ns
         kubectl set env deployment/fulfillment FAILURE_RATE=30 -n $ns
    done
    
    # Wait 10 minutes
    sleep 600

    echo "Fault OFF"
    for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
         kubectl set env deployment/orders FAILURE_RATE- -n $ns
         kubectl set env deployment/fulfillment FAILURE_RATE- -n $ns
    done
    
    # 6. Send Deployment Finished (Good)
    send_sdlc_event "finished" "v1.0.0-blue"
    
    echo "Rollback complete."
}

if [ "$1" == "manual" ]; then
    run_simulation
    exit 0
fi

# Loop forever
while true; do
    # Sleep for random time between 2.5 and 3.5 hours (9000 to 12600 seconds)
    sleep_time=$((9000 + RANDOM % 3600))
    echo "Sleeping for ${sleep_time} seconds..."
    sleep $sleep_time
    
    run_simulation
done

#!/bin/bash

DT_API_URL="${DT_API_URL}"
DT_API_TOKEN="${DT_API_TOKEN}"

# Function to send SDLC event
send_sdlc_event() {
    local status=$1
    local version=$2
    local name="Deploy Services ${version}"
    
    # Current time in nanoseconds
    local timestamp=$(date +%s)000000000
    
    echo "Sending deployment ${status} event for ${version}..."

    payload=$(cat <<EOF
{
  "event.kind": "SDLC_EVENT",
  "event.category": "task",
  "event.type": "deployment",
  "event.status": "${status}",
  "event.provider": "ArgoCD",
  "cicd.deployment.name": "${name}",
  "cicd.deployment.status": "succeeded",
  "cicd.deployment.release_stage": "production",
  "service.version": "${version}",
  "timestamp": "${timestamp}"
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
    send_sdlc_event "started" "v2.0.0-bad"
    
    # 2. Patch Deployments to Bad State
    echo "Patching deployments to FAILURE_MODE=true..."
    for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
        kubectl set env deployment/orders FAILURE_MODE=true -n $ns
        kubectl set env deployment/fulfillment FAILURE_MODE=true -n $ns
    done
    
    # 3. Send Deployment Finished (Bad)
    send_sdlc_event "finished" "v2.0.0-bad"
    
    echo "Bad version deployed. Waiting 5 minutes..."
    sleep 300
    
    echo "Rolling back..."
    
    # 4. Send Deployment Started (Rollback)
    send_sdlc_event "started" "v1.0.0-stable"

    # 5. Patch Deployments to Good State
    echo "Patching deployments to FAILURE_MODE=false..."
    for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
        kubectl set env deployment/orders FAILURE_MODE- -n $ns
        kubectl set env deployment/fulfillment FAILURE_MODE- -n $ns
    done
    
    # 6. Send Deployment Finished (Good)
    send_sdlc_event "finished" "v1.0.0-stable"
    
    echo "Rollback complete."
}

if [ "$1" == "manual" ]; then
    run_simulation
    exit 0
fi

# Loop forever
while true; do
    # Sleep for random time between 2 and 4 hours
    sleep_time=$((7200 + RANDOM % 7200))
    echo "Sleeping for ${sleep_time} seconds..."
    sleep $sleep_time
    
    run_simulation
done

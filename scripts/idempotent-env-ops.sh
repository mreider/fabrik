#!/bin/bash

# Idempotent Environment Variable Operations
# Safe to run multiple times, only makes changes when necessary

set_env_if_different() {
    local namespace=$1
    local deployment=$2
    local env_var=$3
    local new_value=$4

    # Get current value (if any)
    local current_value=$(kubectl get deployment $deployment -n $namespace -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='$env_var')].value}" 2>/dev/null || echo "")

    if [[ "$current_value" != "$new_value" ]]; then
        echo "Setting $deployment/$env_var=$new_value in $namespace (was: $current_value)"
        kubectl set env deployment/$deployment $env_var=$new_value -n $namespace
        return 0
    else
        echo "✓ $deployment/$env_var already set to $new_value in $namespace"
        return 1
    fi
}

unset_env_if_exists() {
    local namespace=$1
    local deployment=$2
    local env_var=$3

    # Check if env var exists
    local current_value=$(kubectl get deployment $deployment -n $namespace -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='$env_var')].value}" 2>/dev/null || echo "")

    if [[ -n "$current_value" ]]; then
        echo "Unsetting $deployment/$env_var in $namespace (was: $current_value)"
        kubectl set env deployment/$deployment $env_var- -n $namespace
        return 0
    else
        echo "✓ $deployment/$env_var already unset in $namespace"
        return 1
    fi
}

check_deployment_ready() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-300}

    echo "Checking if $deployment is ready in $namespace..."
    if kubectl rollout status deployment/$deployment -n $namespace --timeout=${timeout}s >/dev/null 2>&1; then
        echo "✓ $deployment is ready in $namespace"
        return 0
    else
        echo "⚠ $deployment not ready in $namespace within ${timeout}s"
        return 1
    fi
}

restart_deployment_if_needed() {
    local namespace=$1
    local deployment=$2
    local force=${3:-false}

    if [[ "$force" == "true" ]]; then
        echo "Force restarting $deployment in $namespace"
        kubectl rollout restart deployment/$deployment -n $namespace
        return 0
    fi

    # Check if restart is needed (e.g., if there are pending changes)
    local revision=$(kubectl rollout history deployment/$deployment -n $namespace | tail -n 1 | awk '{print $1}')
    local current_revision=$(kubectl get deployment $deployment -n $namespace -o jsonpath='{.status.observedGeneration}')

    if [[ "$revision" != "$current_revision" ]]; then
        echo "Restarting $deployment in $namespace (revision mismatch)"
        kubectl rollout restart deployment/$deployment -n $namespace
        return 0
    else
        echo "✓ $deployment in $namespace doesn't need restart"
        return 1
    fi
}

# Export functions for use in other scripts
export -f set_env_if_different
export -f unset_env_if_exists
export -f check_deployment_ready
export -f restart_deployment_if_needed
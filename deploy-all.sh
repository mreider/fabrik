#!/bin/bash
set -e

echo "Deploying All Fabrik Permutations for Dynatrace Topology Testing..."

# Create namespaces
echo "Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

echo "Ensuring dynatrace namespace exists..."
kubectl create namespace dynatrace || echo "Namespace dynatrace already exists or error creating it."

# --- BEGIN Dynatrace Operator Deployment ---
echo "Deploying Dynatrace Operator..."

# dynatrace namespace is expected to exist at this point
echo "Installing Dynatrace Operator without CSI..."
kubectl apply -f https://github.com/Dynatrace/dynatrace-operator/releases/download/v1.6.1/kubernetes.yaml

echo "Waiting for Dynatrace Operator webhook to be ready..."
kubectl -n dynatrace wait pod --for=condition=ready --selector=app.kubernetes.io/name=dynatrace-operator,app.kubernetes.io/component=webhook --timeout=300s

echo "Applying Dynatrace Operator secret (k8s/dynakube-operator-secret.yaml) to dynatrace namespace..."
echo "NOTE: Ensure you have created 'k8s/dynakube-operator-secret.yaml' from the template and filled in your tokens."
kubectl apply -f k8s/dynakube-operator-secret.yaml -n dynatrace

echo "Applying DynaKube custom resource..."
kubectl apply -f k8s/dynakube.yaml -n dynatrace
# --- END Dynatrace Operator Deployment ---

# Create Dynatrace secrets in required namespaces
echo "Creating Dynatrace secrets..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-enriched
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-standalone
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-collector

# Deploy OpenTelemetry Collector first
echo "Deploying OpenTelemetry Collector..."
kubectl apply -f k8s/fabrik-otel-collector/collector-config.yaml
kubectl apply -f k8s/fabrik-otel-collector/collector.yaml

# Wait for collector to be ready
echo "Waiting for OpenTelemetry Collector to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/otel-collector -n fabrik-otel-collector

# Deploy Redis instances
echo "Deploying Redis instances..."
kubectl apply -f k8s/fabrik-oneagent/redis.yaml
kubectl apply -f k8s/fabrik-otel-enriched/redis.yaml
kubectl apply -f k8s/fabrik-otel-standalone/redis.yaml
kubectl apply -f k8s/fabrik-otel-collector/redis.yaml

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy all application permutations
echo "Deploying all application permutations..."

echo "  - Deploying All-OneAgent (fabrik-oneagent)..."
kubectl apply -f k8s/fabrik-oneagent/fabrik-service.yaml
kubectl apply -f k8s/fabrik-oneagent/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-oneagent/fabrik-frontend.yaml

echo "  - Deploying All-OpenTelemetry with Enrichment (fabrik-otel-enriched)..."
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-frontend.yaml

echo "  - Deploying All-OpenTelemetry Standalone (fabrik-otel-standalone)..."
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-frontend.yaml

echo "  - Deploying OpenTelemetry with Collector (fabrik-otel-collector)..."
kubectl apply -f k8s/fabrik-otel-collector/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-collector/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-collector/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-oneagent
kubectl rollout restart deployment -n fabrik-otel-enriched
kubectl rollout restart deployment -n fabrik-otel-standalone
kubectl rollout restart deployment -n fabrik-otel-collector

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-oneagent --timeout=300s
kubectl rollout status deployment -n fabrik-otel-enriched --timeout=300s
kubectl rollout status deployment -n fabrik-otel-standalone --timeout=300s
kubectl rollout status deployment -n fabrik-otel-collector --timeout=300s

echo "All deployments completed successfully!"
echo ""
echo "Available namespaces:"
echo "  - fabrik-oneagent: All services with OneAgent instrumentation"
echo "  - fabrik-otel-enriched: All services with OpenTelemetry + Dynatrace enrichment"
echo "  - fabrik-otel-standalone: All services with OpenTelemetry, no enrichment"
echo "  - fabrik-otel-collector: All services with OpenTelemetry via Collector + K8s enrichment"
echo ""
echo "To check the status of all deployments, run:"
echo "kubectl get pods -n fabrik-oneagent -n fabrik-otel-enriched -n fabrik-otel-standalone -n fabrik-otel-collector"
echo ""
echo "Test commands for each permutation:"
echo "# OneAgent:"
echo "kubectl port-forward -n fabrik-oneagent svc/fabrik-frontend 8080:8080"
echo "# OpenTelemetry Enriched:"
echo "kubectl port-forward -n fabrik-otel-enriched svc/fabrik-frontend 8081:8080"
echo "# OpenTelemetry Standalone:"
echo "kubectl port-forward -n fabrik-otel-standalone svc/fabrik-frontend 8082:8080"
echo "# OpenTelemetry Collector:"
echo "kubectl port-forward -n fabrik-otel-collector svc/fabrik-frontend 8083:8080"
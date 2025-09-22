#!/bin/bash
set -e

echo "Deploying Fabrik All-OpenTelemetry with Dynatrace Enrichment..."

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

# Create Dynatrace secret in fabrik-otel-enriched namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-enriched

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f k8s/fabrik-otel-enriched/redis.yaml

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy application components
echo "Deploying applications to fabrik-otel-enriched namespace..."
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-enriched/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-otel-enriched

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-otel-enriched --timeout=300s

echo "OpenTelemetry with enrichment deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik-otel-enriched"
echo ""
echo "To test the application:"
echo "kubectl port-forward -n fabrik-otel-enriched svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "curl http://localhost:8080/api/load"
echo "curl http://localhost:8080/health"
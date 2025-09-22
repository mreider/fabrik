#!/bin/bash
set -e

echo "Deploying Fabrik All-OpenTelemetry Standalone (No Dynatrace Enrichment)..."

# Create namespaces
echo "Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

# Create Dynatrace secret in fabrik-otel-standalone namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-standalone

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f k8s/fabrik-otel-standalone/redis.yaml

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy application components
echo "Deploying applications to fabrik-otel-standalone namespace..."
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-standalone/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-otel-standalone

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-otel-standalone --timeout=300s

echo "OpenTelemetry standalone deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik-otel-standalone"
echo ""
echo "To test the application:"
echo "kubectl port-forward -n fabrik-otel-standalone svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "curl http://localhost:8080/api/load"
echo "curl http://localhost:8080/health"
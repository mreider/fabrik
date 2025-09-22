#!/bin/bash
set -e

echo "Deploying Fabrik with OpenTelemetry Collector..."

# Create namespaces
echo "Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

# Create Dynatrace secret in fabrik-otel-collector namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel-collector

# Deploy OpenTelemetry Collector first
echo "Deploying OpenTelemetry Collector..."
kubectl apply -f k8s/fabrik-otel-collector/collector-config.yaml
kubectl apply -f k8s/fabrik-otel-collector/collector.yaml

# Wait for collector to be ready
echo "Waiting for OpenTelemetry Collector to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/otel-collector -n fabrik-otel-collector

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f k8s/fabrik-otel-collector/redis.yaml

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy application components
echo "Deploying applications to fabrik-otel-collector namespace..."
kubectl apply -f k8s/fabrik-otel-collector/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel-collector/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel-collector/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-otel-collector

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-otel-collector --timeout=300s

echo "OpenTelemetry Collector deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik-otel-collector"
echo ""
echo "To test the application:"
echo "kubectl port-forward -n fabrik-otel-collector svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "curl http://localhost:8080/api/load"
echo "curl http://localhost:8080/health"
echo ""
echo "To check OpenTelemetry Collector logs:"
echo "kubectl logs -n fabrik-otel-collector deployment/otel-collector"
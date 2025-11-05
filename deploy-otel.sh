#!/bin/bash
set -e

echo "Deploying Fabrik OpenTelemetry Instrumentation with Dynatrace Enrichment..."

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

# Create Dynatrace secret in fabrik-otel namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel

# Deploy infrastructure
echo "Deploying infrastructure (Redis, MySQL, RabbitMQ, Nginx)..."
kubectl apply -f k8s/fabrik-otel/redis.yaml
kubectl apply -f k8s/fabrik-otel/mysql.yaml
kubectl apply -f k8s/fabrik-otel/rabbitmq.yaml
kubectl apply -f k8s/fabrik-otel/nginx.yaml

# Wait for infrastructure to be ready
echo "Waiting for infrastructure to be ready..."
sleep 30

# Deploy application components
echo "Deploying applications to fabrik-otel namespace..."
kubectl apply -f k8s/fabrik-otel/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-otel

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-otel --timeout=300s

echo "OpenTelemetry deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik-otel"
echo ""
echo "To test the application:"
echo "kubectl port-forward -n fabrik-otel svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "curl http://localhost:8080/api/load"
echo "curl http://localhost:8080/health"
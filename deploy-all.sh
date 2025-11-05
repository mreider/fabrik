#!/bin/bash
set -e

echo "Deploying Simplified Fabrik - OneAgent vs OpenTelemetry Comparison..."

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

# Create Dynatrace secret in both namespaces
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-oneagent

# Deploy infrastructure (Redis, MySQL, RabbitMQ, Nginx)
echo "Deploying infrastructure (Redis, MySQL, RabbitMQ, Nginx)..."
kubectl apply -f k8s/fabrik-oneagent/redis.yaml
kubectl apply -f k8s/fabrik-oneagent/mysql.yaml
kubectl apply -f k8s/fabrik-oneagent/rabbitmq.yaml
kubectl apply -f k8s/fabrik-oneagent/nginx.yaml
kubectl apply -f k8s/fabrik-otel/redis.yaml
kubectl apply -f k8s/fabrik-otel/mysql.yaml
kubectl apply -f k8s/fabrik-otel/rabbitmq.yaml
kubectl apply -f k8s/fabrik-otel/nginx.yaml

# Wait for infrastructure to be ready
echo "Waiting for infrastructure to be ready..."
sleep 30

# Deploy both instrumentation approaches
echo "Deploying applications for instrumentation comparison..."

echo "  - Deploying OneAgent instrumentation (fabrik-oneagent)..."
kubectl apply -f k8s/fabrik-oneagent/fabrik-service.yaml
kubectl apply -f k8s/fabrik-oneagent/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-oneagent/fabrik-frontend.yaml

echo "  - Deploying OpenTelemetry instrumentation (fabrik-otel)..."
kubectl apply -f k8s/fabrik-otel/fabrik-service.yaml
kubectl apply -f k8s/fabrik-otel/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-otel/fabrik-frontend.yaml

# Restart deployments to ensure they pick up any configuration changes
echo "Restarting deployments to pick up configuration changes..."
kubectl rollout restart deployment -n fabrik-oneagent
kubectl rollout restart deployment -n fabrik-otel

# Wait for rollouts to complete
echo "Waiting for rollouts to complete..."
kubectl rollout status deployment -n fabrik-oneagent --timeout=300s
kubectl rollout status deployment -n fabrik-otel --timeout=300s

echo "All deployments completed successfully!"
echo ""
echo "Available namespaces for instrumentation comparison:"
echo "  - fabrik-oneagent: Pure OneAgent instrumentation (no OpenTelemetry code)"
echo "  - fabrik-otel: Pure OpenTelemetry instrumentation with Dynatrace enrichment"
echo ""
echo "To check the status of all deployments, run:"
echo "kubectl get pods -n fabrik-oneagent -n fabrik-otel"
echo ""
echo "Test commands for each instrumentation approach:"
echo ""
echo "# OneAgent (pure Dynatrace OneAgent, no OTel):"
echo "# Direct service access:"
echo "kubectl port-forward -n fabrik-oneagent svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "# Via nginx proxy:"
echo "kubectl port-forward -n fabrik-oneagent svc/nginx 8090:80"
echo "curl http://localhost:8090/api/call-proxy"
echo "curl http://localhost:8090/nginx-health"
echo ""
echo "# OpenTelemetry (with Dynatrace enrichment):"
echo "# Direct service access:"
echo "kubectl port-forward -n fabrik-otel svc/fabrik-frontend 8081:8080"
echo "curl http://localhost:8081/api/call-proxy"
echo "# Via nginx proxy (with OTel instrumentation):"
echo "kubectl port-forward -n fabrik-otel svc/nginx 8091:80"
echo "curl http://localhost:8091/api/call-proxy"
echo "curl http://localhost:8091/nginx-health"
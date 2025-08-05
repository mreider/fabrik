#!/bin/bash
set -e

# Create namespaces
echo "Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

echo "Ensuring dynatrace namespace exists..."
kubectl create namespace dynatrace || echo "Namespace dynatrace already exists or error creating it."

# --- BEGIN Dynatrace Operator Deployment ---
echo "Deploying Dynatrace Operator..."

# dynatrace namespace is expected to exist at this point
echo "Installing Dynatrace Operator with CSI..."
kubectl apply -f https://github.com/Dynatrace/dynatrace-operator/releases/download/v1.5.1/kubernetes-csi.yaml

echo "Waiting for Dynatrace Operator webhook to be ready..."
kubectl -n dynatrace wait pod --for=condition=ready --selector=app.kubernetes.io/name=dynatrace-operator,app.kubernetes.io/component=webhook --timeout=300s

echo "Applying Dynatrace Operator secret (k8s/dynakube-operator-secret.yaml) to dynatrace namespace..."
echo "NOTE: Ensure you have created 'k8s/dynakube-operator-secret.yaml' from the template and filled in your tokens."
kubectl apply -f k8s/dynakube-operator-secret.yaml -n dynatrace

echo "Applying DynaKube custom resource..."
kubectl apply -f k8s/dynakube.yaml -n dynatrace
# --- END Dynatrace Operator Deployment ---

# Create Dynatrace secret in each namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-otel
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik-oneagent

# Deploy Redis in both namespaces
echo "Deploying Redis..."
kubectl apply -f k8s/redis.yaml -n fabrik-otel
kubectl apply -f k8s/redis.yaml -n fabrik-oneagent

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy application components for fabrik-otel namespace
echo "Deploying applications to fabrik-otel namespace..."
kubectl apply -f k8s/otel-fabrik-service.yaml
kubectl apply -f k8s/otel-fabrik-proxy.yaml

# Deploy application components for fabrik-oneagent namespace
echo "Deploying applications to fabrik-oneagent namespace..."
kubectl apply -f k8s/oneagent-fabrik-service.yaml
kubectl apply -f k8s/oneagent-fabrik-proxy.yaml

echo "Deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik-otel"
echo "kubectl get pods -n fabrik-oneagent"
echo ""
echo "To test the applications:"
echo "# Port forward to test fabrik-otel:"
echo "kubectl port-forward -n fabrik-otel svc/fabrik-proxy 8080:8080"
echo "curl http://localhost:8080/api/proxy"
echo "curl http://localhost:8080/api/load"
echo ""
echo "# Port forward to test fabrik-oneagent:"
echo "kubectl port-forward -n fabrik-oneagent svc/fabrik-proxy 8081:8080"
echo "curl http://localhost:8081/api/proxy"
echo "curl http://localhost:8081/api/load"

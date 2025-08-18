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

# Create Dynatrace secret in fabrik namespace
echo "Creating Dynatrace secret..."
kubectl apply -f k8s/dynatrace-secret.yaml -n fabrik

# Deploy Redis
echo "Deploying Redis..."
kubectl apply -f k8s/redis.yaml

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
sleep 15

# Deploy application components
echo "Deploying applications to fabrik namespace..."
kubectl apply -f k8s/fabrik-service.yaml
kubectl apply -f k8s/fabrik-proxy.yaml
kubectl apply -f k8s/fabrik-frontend.yaml

echo "Deployment completed successfully!"
echo "To check the status of the deployments, run:"
echo "kubectl get pods -n fabrik"
echo ""
echo "To test the application:"
echo "kubectl port-forward -n fabrik svc/fabrik-frontend 8080:8080"
echo "curl http://localhost:8080/api/call-proxy"
echo "curl http://localhost:8080/api/load"
echo "curl http://localhost:8080/health"
echo ""
echo "To test fabrik-proxy directly:"
echo "kubectl port-forward -n fabrik svc/fabrik-proxy 8081:8080"
echo "curl http://localhost:8081/api/proxy"
echo "curl http://localhost:8081/health"
echo ""
echo "To test fabrik-service directly:"
echo "kubectl port-forward -n fabrik svc/fabrik-service 8082:8080"
echo "curl http://localhost:8082/api/process"
echo "curl http://localhost:8082/api/redis/stats"
echo "curl http://localhost:8082/api/redis/cleanup"

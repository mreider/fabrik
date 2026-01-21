#!/bin/bash
set -e

echo "Deploying Fabrik Demo..."

# Create namespaces
kubectl apply -f k8s/namespaces.yaml

# Create Dynatrace namespace if not exists (usually created by Operator, but we need it for Secret)
kubectl create namespace dynatrace --dry-run=client -o yaml | kubectl apply -f -

# Install Dynatrace Operator
echo "Installing Dynatrace Operator..."
kubectl apply -f https://github.com/Dynatrace/dynatrace-operator/releases/download/v1.6.1/kubernetes.yaml

echo "Waiting for Dynatrace Operator webhook to be ready..."
kubectl -n dynatrace wait pod --for=condition=ready --selector=app.kubernetes.io/name=dynatrace-operator,app.kubernetes.io/component=webhook --timeout=300s

# Apply Secrets (gitignored)
if [ -f "k8s/secrets.yaml" ]; then
  kubectl apply -f k8s/secrets.yaml
else
  echo "Error: k8s/secrets.yaml not found. Please create it with the required secrets."
  exit 1
fi

# Apply Dynakube
kubectl apply -f k8s/dynakube.yaml

# Apply Applications
kubectl apply -f k8s/fabrik-oa.yaml
kubectl apply -f k8s/fabrik-ot.yaml
kubectl apply -f k8s/fabrik-oa-2.yaml

# Restart deployments to pick up changes
kubectl rollout restart deployment -n fabrik-oa
kubectl rollout restart deployment -n fabrik-ot
kubectl rollout restart deployment -n fabrik-oa-2

echo "Deployment complete."

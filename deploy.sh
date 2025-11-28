#!/bin/bash
set -e

if [ -z "$DT_API_TOKEN" ]; then
  echo "Error: DT_API_TOKEN environment variable is not set."
  exit 1
fi

echo "Deploying Fabrik Demo..."

# Create namespaces
kubectl apply -f k8s/namespaces.yaml

# Create Dynatrace namespace if not exists (usually created by Operator, but we need it for Secret)
kubectl create namespace dynatrace --dry-run=client -o yaml | kubectl apply -f -

# Create Dynakube Secret
kubectl -n dynatrace create secret generic dynakube \
  --from-literal="apiToken=$DT_API_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

# Create OTel Secret
kubectl -n fabrik-ot create secret generic dynatrace-otel-secret \
  --from-literal="auth-header=Authorization=Api-Token $DT_API_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

# Apply Dynakube
kubectl apply -f k8s/dynakube.yaml

# Apply Applications
kubectl apply -f k8s/fabrik-oa.yaml
kubectl apply -f k8s/fabrik-ot.yaml

echo "Deployment complete."

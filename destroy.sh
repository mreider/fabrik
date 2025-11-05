#!/bin/bash
set -e

echo "Destroying Fabrik application..."

# Delete application deployments
echo "Deleting application deployments..."
kubectl delete namespace fabrik-oneagent --ignore-not-found=true
kubectl delete namespace fabrik-otel --ignore-not-found=true

echo "Fabrik application destroyed successfully!"
echo ""
echo "Note: Dynatrace Operator and dynatrace namespace are left intact."
echo "To completely remove Dynatrace Operator, run:"
echo "kubectl delete namespace dynatrace"
echo "kubectl delete -f https://github.com/Dynatrace/dynatrace-operator/releases/download/v1.5.1/kubernetes-csi.yaml"

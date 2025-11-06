#!/bin/bash

set -e

echo "🧹 Destroying Fabrik Demo Applications"
echo "======================================"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl could not be found. Please install kubectl."
    exit 1
fi

echo "🗑️ Removing Fabrik Demo components..."

# Delete applications first
echo "   Removing applications..."
kubectl delete -f k8s/fabrik-1/ --ignore-not-found=true 2>/dev/null || true
kubectl delete -f k8s/fabrik-2/ --ignore-not-found=true 2>/dev/null || true

# Delete infrastructure
echo "   Removing infrastructure..."
kubectl delete -f k8s/infrastructure/ --ignore-not-found=true 2>/dev/null || true

# Delete namespaces (this will clean up any remaining resources)
echo "   Removing namespaces..."
kubectl delete -f k8s/namespaces.yaml --ignore-not-found=true 2>/dev/null || true

echo ""
echo "⏳ Waiting for namespaces to be fully deleted..."

# Wait for namespaces to be fully deleted
for namespace in fabrik-1 fabrik-2; do
    while kubectl get namespace $namespace &>/dev/null; do
        echo "   Still deleting namespace $namespace..."
        sleep 5
    done
done

echo ""
echo "✅ Fabrik Demo cleanup completed successfully!"
echo ""
echo "📝 Status:"
echo "   ✓ All applications removed"
echo "   ✓ All infrastructure removed"
echo "   ✓ Namespaces deleted"
echo ""
echo "🔧 Note: Dynatrace Operator and dynatrace namespace are preserved."
echo "   To remove Dynatrace components completely:"
echo "   kubectl delete namespace dynatrace"
echo ""
echo "🚀 Ready for fresh deployment with: ./deploy-fabrik-demo.sh"
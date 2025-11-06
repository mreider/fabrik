#!/bin/bash

set -e

echo "🚀 Deploying Fabrik Demo - OneAgent vs OpenTelemetry Comparison"
echo "=================================================================="
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl could not be found. Please install kubectl and configure your cluster access."
    exit 1
fi

# Check if we can access the cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot access Kubernetes cluster. Please check your kubectl configuration."
    exit 1
fi

echo "✅ Kubernetes cluster access confirmed"
echo ""

# Function to wait for deployment to be ready
wait_for_deployment() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-300}

    echo "⏳ Waiting for deployment $deployment in namespace $namespace..."
    if kubectl wait --for=condition=available --timeout=${timeout}s deployment/$deployment -n $namespace; then
        echo "✅ $deployment is ready"
    else
        echo "⚠️ $deployment took longer than expected to be ready"
    fi
}

# Function to wait for pods to be running
wait_for_pods() {
    local namespace=$1
    local timeout=${2:-300}

    echo "⏳ Waiting for all pods in namespace $namespace to be running..."
    local end_time=$((SECONDS + timeout))

    while [[ $SECONDS -lt $end_time ]]; do
        local not_ready=$(kubectl get pods -n $namespace --no-headers | grep -v Running | wc -l)
        if [[ $not_ready -eq 0 ]]; then
            echo "✅ All pods in $namespace are running"
            return 0
        fi
        echo "   Still waiting... ($not_ready pods not ready)"
        sleep 10
    done

    echo "⚠️ Some pods in $namespace are not ready after ${timeout}s"
    kubectl get pods -n $namespace
}

# Create namespaces
echo "📦 Creating namespaces..."
kubectl apply -f k8s/namespaces.yaml

echo "✅ Namespaces created"
echo ""

# Deploy infrastructure components
echo "🏗️ Deploying infrastructure components..."

echo "   Deploying MySQL databases..."
kubectl apply -f k8s/infrastructure/mysql.yaml

echo "   Deploying RabbitMQ message brokers..."
kubectl apply -f k8s/infrastructure/rabbitmq.yaml

echo "   Deploying NGINX proxies..."
kubectl apply -f k8s/infrastructure/nginx.yaml

echo "✅ Infrastructure deployed"
echo ""

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure to be ready..."
wait_for_deployment "fabrik-1" "mysql" 180
wait_for_deployment "fabrik-1" "rabbitmq" 120
wait_for_deployment "fabrik-1" "nginx" 60

wait_for_deployment "fabrik-2" "mysql" 180
wait_for_deployment "fabrik-2" "rabbitmq" 120
wait_for_deployment "fabrik-2" "nginx" 60

echo "✅ Infrastructure is ready"
echo ""

# Deploy applications
echo "🚀 Deploying applications..."

echo "   Deploying Fabrik-1 (OneAgent instrumentation)..."
kubectl apply -f k8s/fabrik-1/

echo "   Deploying Fabrik-2 (OpenTelemetry instrumentation)..."
kubectl apply -f k8s/fabrik-2/

echo "✅ Applications deployed"
echo ""

# Wait for applications to be ready
echo "⏳ Waiting for applications to be ready..."

echo "   Waiting for Fabrik-1 (OneAgent)..."
wait_for_deployment "fabrik-1" "fabrik-orders" 120
wait_for_deployment "fabrik-1" "fabrik-fulfillment" 120
wait_for_deployment "fabrik-1" "load-generator" 60

echo "   Waiting for Fabrik-2 (OpenTelemetry)..."
wait_for_deployment "fabrik-2" "fabrik-orders" 120
wait_for_deployment "fabrik-2" "fabrik-fulfillment" 120
wait_for_deployment "fabrik-2" "load-generator" 60

echo "✅ Applications are ready"
echo ""

# Final status check
echo "📊 Final status check..."

echo ""
echo "Fabrik-1 (OneAgent) namespace:"
kubectl get pods -n fabrik-1 -o wide

echo ""
echo "Fabrik-2 (OpenTelemetry) namespace:"
kubectl get pods -n fabrik-2 -o wide

echo ""
echo "🎉 Fabrik Demo deployment completed successfully!"
echo ""
echo "📝 Usage Instructions:"
echo "======================"
echo ""
echo "1. Access Fabrik-1 (OneAgent) via NGINX:"
echo "   kubectl port-forward -n fabrik-1 svc/nginx 8080:80"
echo "   curl -X POST http://localhost:8080/orders -H \"Content-Type: application/json\" -d '{\"customer_name\":\"John Doe\",\"product_name\":\"Widget A\",\"quantity\":2,\"unit_price\":25.99}'"
echo ""
echo "2. Access Fabrik-2 (OpenTelemetry) via NGINX:"
echo "   kubectl port-forward -n fabrik-2 svc/nginx 8081:80"
echo "   curl -X POST http://localhost:8081/orders -H \"Content-Type: application/json\" -d '{\"customer_name\":\"Jane Smith\",\"product_name\":\"Gadget X\",\"quantity\":1,\"unit_price\":49.99}'"
echo ""
echo "3. Monitor load generators:"
echo "   kubectl logs -n fabrik-1 deployment/load-generator -f"
echo "   kubectl logs -n fabrik-2 deployment/load-generator -f"
echo ""
echo "4. Check order fulfillment stats:"
echo "   kubectl port-forward -n fabrik-1 svc/fabrik-fulfillment 3001:3001"
echo "   curl http://localhost:3001/stats"
echo ""
echo "5. Access RabbitMQ Management (optional):"
echo "   kubectl port-forward -n fabrik-1 svc/rabbitmq 15672:15672"
echo "   http://localhost:15672 (fabrik/fabrik123)"
echo ""
echo "🔍 Compare the instrumentation differences in Dynatrace:"
echo "   - OneAgent: Automatic instrumentation with zero code changes"
echo "   - OpenTelemetry: Manual instrumentation with full control"
echo ""
echo "🧹 To clean up: ./destroy-fabrik-demo.sh"
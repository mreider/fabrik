#!/bin/bash

# Fabrik Load Generator
# Generates continuous load to test the order processing system

set -e

# Configuration
NGINX_URL="${NGINX_URL:-http://nginx:80}"
INTERVAL_MIN="${INTERVAL_MIN:-2}"
INTERVAL_MAX="${INTERVAL_MAX:-8}"
BATCH_SIZE="${BATCH_SIZE:-1}"
NAMESPACE="${NAMESPACE:-unknown}"

# Product catalog
PRODUCTS=("Widget A" "Widget B" "Widget C" "Gadget X" "Gadget Y" "Device Pro" "Tool Kit" "Premium Set")
CUSTOMERS=("John Smith" "Jane Doe" "Bob Johnson" "Alice Brown" "Charlie Wilson" "Diana Lee" "Frank Miller" "Grace Davis")

echo "🚀 Fabrik Load Generator Starting"
echo "   Target: ${NGINX_URL}/orders"
echo "   Namespace: ${NAMESPACE}"
echo "   Interval: ${INTERVAL_MIN}-${INTERVAL_MAX} seconds"
echo "   Batch size: ${BATCH_SIZE}"
echo ""

generate_order() {
    local customer="${CUSTOMERS[$((RANDOM % ${#CUSTOMERS[@]}))]}"
    local product="${PRODUCTS[$((RANDOM % ${#PRODUCTS[@]}))]}"
    local quantity=$((RANDOM % 5 + 1))
    local unit_price=$(awk "BEGIN {printf \"%.2f\", $((RANDOM % 9000 + 1000)) / 100}")

    cat <<EOF
{
  "customer_name": "${customer}",
  "product_name": "${product}",
  "quantity": ${quantity},
  "unit_price": ${unit_price}
}
EOF
}

# Counter for tracking requests
request_count=0
success_count=0
error_count=0

echo_status() {
    echo "📊 Stats: Total=${request_count}, Success=${success_count}, Errors=${error_count}"
}

# Show stats every 30 requests
show_stats_interval=30

while true; do
    for ((i=1; i<=BATCH_SIZE; i++)); do
        request_count=$((request_count + 1))

        # Generate order payload
        order_data=$(generate_order)

        echo "📦 [${request_count}] Sending order request..."

        # Send POST request to nginx/orders endpoint
        response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
            -X POST \
            -H "Content-Type: application/json" \
            -H "User-Agent: Fabrik-LoadGen/1.0" \
            -H "X-Load-Generator: true" \
            -H "X-Namespace: ${NAMESPACE}" \
            -d "${order_data}" \
            "${NGINX_URL}/orders" \
            2>/dev/null || echo "HTTPSTATUS:000")

        # Extract HTTP status code
        http_status=$(echo "$response" | grep -o 'HTTPSTATUS:[0-9]*' | cut -d: -f2)
        response_body=$(echo "$response" | sed 's/HTTPSTATUS:[0-9]*$//')

        if [[ "$http_status" =~ ^2[0-9][0-9]$ ]]; then
            success_count=$((success_count + 1))
            echo "   ✅ Success ($http_status)"
            # Optionally show order ID if available
            if echo "$response_body" | grep -q "orderId"; then
                order_id=$(echo "$response_body" | grep -o '"orderId":"[^"]*"' | cut -d'"' -f4)
                echo "   📋 Order ID: $order_id"
            fi
        else
            error_count=$((error_count + 1))
            echo "   ❌ Error ($http_status)"
            if [[ -n "$response_body" ]]; then
                echo "   📝 Response: $response_body"
            fi
        fi

        # Show stats periodically
        if (( request_count % show_stats_interval == 0 )); then
            echo ""
            echo_status
            echo ""
        fi

        # Small delay between batch requests
        if [[ $i -lt $BATCH_SIZE ]]; then
            sleep 0.5
        fi
    done

    # Random interval between batches
    interval=$(shuf -i ${INTERVAL_MIN}-${INTERVAL_MAX} -n 1)
    echo "⏱️  Waiting ${interval}s before next batch..."
    sleep $interval
done
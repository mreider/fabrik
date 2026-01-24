"""
Fab Proxy Service - Python version
Load generator that calls frontend service.
"""
import os
import logging
import random
import threading
import time
import requests
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Frontend service URL
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://frontend:8080')

# Load generation settings
LOAD_ENABLED = os.environ.get('LOAD_ENABLED', 'true').lower() == 'true'
LOAD_INTERVAL_MS = int(os.environ.get('LOAD_INTERVAL_MS', '5000'))
LOAD_BATCH_SIZE = int(os.environ.get('LOAD_BATCH_SIZE', '3'))


@app.route('/health', methods=['GET'])
@app.route('/actuator/health', methods=['GET'])
def health():
    return jsonify({'status': 'UP'})


@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        'service': 'fab-proxy-py',
        'loadEnabled': LOAD_ENABLED,
        'loadIntervalMs': LOAD_INTERVAL_MS,
        'loadBatchSize': LOAD_BATCH_SIZE,
        'frontendUrl': FRONTEND_URL
    })


def generate_order():
    """Generate a random order."""
    products = [
        {'name': 'Widget A', 'price': 29.99},
        {'name': 'Widget B', 'price': 49.99},
        {'name': 'Widget C', 'price': 99.99},
        {'name': 'Gadget X', 'price': 149.99},
        {'name': 'Gadget Y', 'price': 199.99},
    ]

    product = random.choice(products)
    quantity = random.randint(1, 5)

    first_names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    customer_name = f"{first_name} {last_name}"
    customer_email = f"{first_name.lower()}.{last_name.lower()}@example.com"

    return {
        'customerName': customer_name,
        'customerEmail': customer_email,
        'product': product['name'],
        'quantity': quantity,
        'price': product['price'] * quantity
    }


def place_order():
    """Place an order via frontend service."""
    order = generate_order()
    try:
        response = requests.post(
            f"{FRONTEND_URL}/api/shop/checkout",
            json=order,
            timeout=120
        )
        if response.status_code in [200, 201]:
            result = response.json()
            order_info = result.get('order', {})
            logger.info(f"Order placed: {order_info.get('id', 'unknown')[:8]}... - {order['product']} x {order['quantity']}")
        else:
            logger.warning(f"Order failed with status {response.status_code}: {response.text[:100]}")
    except requests.exceptions.Timeout:
        logger.error("Frontend timeout while placing order")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to place order: {e}")


def browse_products():
    """Browse products via frontend service."""
    try:
        response = requests.get(f"{FRONTEND_URL}/api/shop/products", timeout=30)
        if response.status_code == 200:
            products = response.json()
            logger.debug(f"Browsed {len(products)} products")
        else:
            logger.warning(f"Browse products failed with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to browse products: {e}")


def check_orders():
    """Check recent orders via frontend service."""
    try:
        response = requests.get(f"{FRONTEND_URL}/api/shop/orders", timeout=30)
        if response.status_code == 200:
            orders = response.json()
            logger.debug(f"Checked {len(orders)} recent orders")
        else:
            logger.warning(f"Check orders failed with status {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to check orders: {e}")


def load_generator_thread():
    """Background thread for load generation."""
    logger.info(f"Load generator starting (interval={LOAD_INTERVAL_MS}ms, batch={LOAD_BATCH_SIZE})")

    # Wait for frontend to be ready
    max_retries = 60
    for i in range(max_retries):
        try:
            response = requests.get(f"{FRONTEND_URL}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Frontend is ready, starting load generation")
                break
        except Exception:
            pass
        logger.info(f"Waiting for frontend (attempt {i+1}/{max_retries})...")
        time.sleep(2)
    else:
        logger.error("Frontend not ready after max retries, starting anyway")

    while True:
        try:
            # Generate batch of requests
            for _ in range(LOAD_BATCH_SIZE):
                # Random action distribution: 60% orders, 25% browse, 15% check orders
                action = random.random()
                if action < 0.60:
                    place_order()
                elif action < 0.85:
                    browse_products()
                else:
                    check_orders()

                # Small delay between requests in batch
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Load generation error: {e}")

        # Wait for next batch
        time.sleep(LOAD_INTERVAL_MS / 1000.0)


def initialize():
    """Start load generator if enabled."""
    if LOAD_ENABLED:
        load_thread = threading.Thread(target=load_generator_thread, daemon=True)
        load_thread.start()
        logger.info("Load generator thread started")
    else:
        logger.info("Load generator disabled")


# Initialize on import for gunicorn
initialize()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

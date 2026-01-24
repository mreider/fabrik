"""
Frontend Service - Python version
REST gateway that calls orders service.
"""
import os
import sys
import logging
import requests
from flask import Flask, request, jsonify

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.chaos import apply_db_slowdown, simulate_latency
from common.db import get_db_connection, init_db_tables

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Orders service URL
ORDERS_SERVICE_URL = os.environ.get('ORDERS_SERVICE_URL', 'http://orders:8080')


@app.route('/health', methods=['GET'])
@app.route('/actuator/health', methods=['GET'])
def health():
    return jsonify({'status': 'UP'})


@app.route('/', methods=['GET'])
def index():
    """Home page."""
    return jsonify({
        'service': 'frontend-py',
        'status': 'running',
        'endpoints': [
            '/api/shop/products',
            '/api/shop/cart',
            '/api/shop/checkout'
        ]
    })


@app.route('/api/shop/products', methods=['GET'])
def get_products():
    """Get available products."""
    simulate_latency(20, 50)
    # Mock product catalog
    products = [
        {'id': '1', 'name': 'Widget A', 'price': 29.99, 'stock': 100},
        {'id': '2', 'name': 'Widget B', 'price': 49.99, 'stock': 50},
        {'id': '3', 'name': 'Widget C', 'price': 99.99, 'stock': 25},
        {'id': '4', 'name': 'Gadget X', 'price': 149.99, 'stock': 10},
        {'id': '5', 'name': 'Gadget Y', 'price': 199.99, 'stock': 5},
    ]
    return jsonify(products)


@app.route('/api/shop/cart', methods=['GET'])
def get_cart():
    """Get shopping cart (mock)."""
    simulate_latency(10, 30)
    return jsonify({'items': [], 'total': 0})


@app.route('/api/shop/checkout', methods=['POST'])
def checkout():
    """Process checkout - calls orders service."""
    # Apply DB slowdown for chaos testing
    conn = None
    try:
        conn = get_db_connection()
        apply_db_slowdown(conn, "checkout")
    except Exception as e:
        logger.warning(f"DB chaos check failed: {e}")
    finally:
        if conn:
            conn.close()

    # Parse checkout request
    data = request.get_json() or {}
    customer_name = data.get('customerName', 'Test Customer')
    customer_email = data.get('customerEmail', 'test@example.com')
    product = data.get('product', 'Widget A')
    quantity = data.get('quantity', 1)
    price = data.get('price', 29.99)

    # Call orders service to place order
    try:
        response = requests.post(
            f"{ORDERS_SERVICE_URL}/api/orders",
            json={
                'customerName': customer_name,
                'customerEmail': customer_email,
                'product': product,
                'quantity': quantity,
                'price': price
            },
            timeout=60
        )
        response.raise_for_status()
        order = response.json()
        logger.info(f"Order placed via orders service: {order.get('id')}")
        return jsonify({
            'success': True,
            'order': order,
            'message': 'Order placed successfully'
        }), 201
    except requests.exceptions.Timeout:
        logger.error("Orders service timeout")
        return jsonify({'success': False, 'error': 'Order service timeout'}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to place order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/shop/orders', methods=['GET'])
def get_my_orders():
    """Get orders from orders service."""
    simulate_latency(30, 80)
    try:
        response = requests.get(f"{ORDERS_SERVICE_URL}/api/orders/recent", timeout=30)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get orders: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/shop/orders/<order_id>', methods=['GET'])
def get_order_status(order_id):
    """Get order status from orders service."""
    simulate_latency(10, 30)
    try:
        response = requests.get(f"{ORDERS_SERVICE_URL}/api/orders/{order_id}", timeout=30)
        if response.status_code == 404:
            return jsonify({'error': 'Order not found'}), 404
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get order: {e}")
        return jsonify({'error': str(e)}), 500


def initialize():
    """Initialize database tables on startup."""
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            init_db_tables(conn)
            conn.close()
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            logger.warning(f"Database not ready (attempt {i+1}/{max_retries}): {e}")
            import time
            time.sleep(2)
    logger.error("Failed to initialize database after max retries")


# Initialize on import for gunicorn
initialize()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

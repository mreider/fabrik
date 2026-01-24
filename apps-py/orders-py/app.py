"""
Orders Service - Python version
REST API for order management with Kafka producer.
"""
import os
import sys
import uuid
import json
import logging
import random
from datetime import datetime
from flask import Flask, request, jsonify

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.chaos import apply_slowdown, apply_db_slowdown, simulate_latency
from common.db import get_db_connection, init_db_tables

from kafka import KafkaProducer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Kafka producer (lazy initialization)
_kafka_producer = None


def get_kafka_producer():
    global _kafka_producer
    if _kafka_producer is None:
        bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        _kafka_producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode('utf-8') if isinstance(v, str) else v
        )
    return _kafka_producer


def send_to_kafka(topic: str, message: str):
    """Send message to Kafka topic."""
    producer = get_kafka_producer()
    producer.send(topic, message)
    producer.flush()
    logger.info(f"Sent to {topic}: {message}")


@app.route('/health', methods=['GET'])
@app.route('/actuator/health', methods=['GET'])
def health():
    return jsonify({'status': 'UP'})


@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Get all orders."""
    simulate_latency(50, 150)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, customer_email, product, quantity, price, status, created_at FROM orders ORDER BY created_at DESC LIMIT 100")
    orders = []
    for row in cursor.fetchall():
        orders.append({
            'id': row[0],
            'customerName': row[1],
            'customerEmail': row[2],
            'product': row[3],
            'quantity': row[4],
            'price': float(row[5]) if row[5] else 0,
            'status': row[6],
            'createdAt': row[7].isoformat() if row[7] else None
        })
    cursor.close()
    conn.close()
    return jsonify(orders)


@app.route('/api/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    """Get order by ID."""
    simulate_latency(10, 40)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, customer_email, product, quantity, price, status, created_at FROM orders WHERE id = %s", (order_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({'error': 'Order not found'}), 404

    return jsonify({
        'id': row[0],
        'customerName': row[1],
        'customerEmail': row[2],
        'product': row[3],
        'quantity': row[4],
        'price': float(row[5]) if row[5] else 0,
        'status': row[6],
        'createdAt': row[7].isoformat() if row[7] else None
    })


@app.route('/api/orders/recent', methods=['GET'])
def get_recent_orders():
    """Get recent orders."""
    simulate_latency(20, 60)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, customer_email, product, quantity, price, status, created_at FROM orders ORDER BY created_at DESC LIMIT 10")
    orders = []
    for row in cursor.fetchall():
        orders.append({
            'id': row[0],
            'customerName': row[1],
            'customerEmail': row[2],
            'product': row[3],
            'quantity': row[4],
            'price': float(row[5]) if row[5] else 0,
            'status': row[6],
            'createdAt': row[7].isoformat() if row[7] else None
        })
    cursor.close()
    conn.close()
    return jsonify(orders)


@app.route('/api/orders/status/<status>', methods=['GET'])
def get_orders_by_status(status):
    """Get orders by status."""
    simulate_latency(80, 180)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, customer_name, customer_email, product, quantity, price, status, created_at FROM orders WHERE status = %s ORDER BY created_at DESC", (status,))
    orders = []
    for row in cursor.fetchall():
        orders.append({
            'id': row[0],
            'customerName': row[1],
            'customerEmail': row[2],
            'product': row[3],
            'quantity': row[4],
            'price': float(row[5]) if row[5] else 0,
            'status': row[6],
            'createdAt': row[7].isoformat() if row[7] else None
        })
    cursor.close()
    conn.close()
    return jsonify(orders)


@app.route('/api/orders/stats', methods=['GET'])
def get_order_stats():
    """Get order statistics."""
    simulate_latency(300, 700)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
    stats = {}
    for row in cursor.fetchall():
        stats[row[0]] = row[1]
    cursor.close()
    conn.close()
    return jsonify(stats)


@app.route('/api/orders', methods=['POST'])
def place_order():
    """Place a new order - main endpoint with chaos patterns."""
    order_id = str(uuid.uuid4())

    # Pattern 1: Service Slowdown
    apply_slowdown(f"order {order_id[:8]}")

    # Pattern 2: DB Slowdown (heavy query)
    conn = get_db_connection()
    apply_db_slowdown(conn, f"order {order_id[:8]}")

    # Parse request
    data = request.get_json() or {}
    customer_name = data.get('customerName', 'Test Customer')
    customer_email = data.get('customerEmail', 'test@example.com')
    product = data.get('product', 'Widget')
    quantity = data.get('quantity', 1)
    price = data.get('price', 99.99)

    # Save order to database
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (id, customer_name, customer_email, product, quantity, price, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (order_id, customer_name, customer_email, product, quantity, price, 'PENDING')
    )
    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"Order created: {order_id}")

    # Send to Kafka
    try:
        send_to_kafka('orders', order_id)
        send_to_kafka('order-updates', f"{order_id}:CREATED")
    except Exception as e:
        logger.error(f"Failed to send to Kafka: {e}")

    return jsonify({
        'id': order_id,
        'customerName': customer_name,
        'customerEmail': customer_email,
        'product': product,
        'quantity': quantity,
        'price': price,
        'status': 'PENDING'
    }), 201


@app.route('/api/orders/<order_id>/cancel', methods=['PUT'])
def cancel_order(order_id):
    """Cancel an order."""
    simulate_latency(100, 200)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = %s WHERE id = %s", ('CANCELLED', order_id))
    conn.commit()
    rows_updated = cursor.rowcount
    cursor.close()
    conn.close()

    if rows_updated == 0:
        return jsonify({'error': 'Order not found'}), 404

    # Send update to Kafka
    try:
        send_to_kafka('order-updates', f"{order_id}:CANCELLED")
    except Exception as e:
        logger.error(f"Failed to send to Kafka: {e}")

    return jsonify({'id': order_id, 'status': 'CANCELLED'})


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

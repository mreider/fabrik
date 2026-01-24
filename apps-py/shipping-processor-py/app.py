"""
Shipping Processor Service - Python version
REST API for shipment processing with Kafka producer.
"""
import os
import sys
import uuid
import logging
import random
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


@app.route('/api/shipments', methods=['GET'])
def get_shipments():
    """Get all shipments."""
    simulate_latency(30, 80)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_id, carrier, tracking_number, status, created_at FROM shipments ORDER BY created_at DESC LIMIT 100")
    shipments = []
    for row in cursor.fetchall():
        shipments.append({
            'id': row[0],
            'orderId': row[1],
            'carrier': row[2],
            'trackingNumber': row[3],
            'status': row[4],
            'createdAt': row[5].isoformat() if row[5] else None
        })
    cursor.close()
    conn.close()
    return jsonify(shipments)


@app.route('/api/shipments/<shipment_id>', methods=['GET'])
def get_shipment(shipment_id):
    """Get shipment by ID."""
    simulate_latency(10, 30)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_id, carrier, tracking_number, status, created_at FROM shipments WHERE id = %s", (shipment_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({'error': 'Shipment not found'}), 404

    return jsonify({
        'id': row[0],
        'orderId': row[1],
        'carrier': row[2],
        'trackingNumber': row[3],
        'status': row[4],
        'createdAt': row[5].isoformat() if row[5] else None
    })


@app.route('/api/shipments', methods=['POST'])
def create_shipment():
    """Create a new shipment - main endpoint with chaos patterns."""
    shipment_id = str(uuid.uuid4())

    # Parse request
    data = request.get_json() or {}
    order_id = data.get('orderId', str(uuid.uuid4()))

    # Pattern 1: Service Slowdown
    apply_slowdown(f"shipment {shipment_id[:8]}")

    # Pattern 2: DB Slowdown (heavy query)
    conn = get_db_connection()
    apply_db_slowdown(conn, f"shipment {shipment_id[:8]}")

    # Generate shipment details
    carriers = ['FedEx', 'UPS', 'USPS', 'DHL']
    carrier = random.choice(carriers)
    tracking_number = f"{carrier[:2].upper()}{random.randint(100000000, 999999999)}"

    # Save shipment to database
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO shipments (id, order_id, carrier, tracking_number, status) VALUES (%s, %s, %s, %s, %s)",
        (shipment_id, order_id, carrier, tracking_number, 'CREATED')
    )
    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"Shipment created: {shipment_id} for order {order_id}")

    # Send to Kafka
    try:
        send_to_kafka('shipments', f"{shipment_id}:{order_id}:CREATED")
        send_to_kafka('order-updates', f"{order_id}:SHIPMENT_CREATED")
    except Exception as e:
        logger.error(f"Failed to send to Kafka: {e}")

    return jsonify({
        'id': shipment_id,
        'orderId': order_id,
        'carrier': carrier,
        'trackingNumber': tracking_number,
        'status': 'CREATED'
    }), 201


@app.route('/api/shipments/<shipment_id>/ship', methods=['PUT'])
def ship_shipment(shipment_id):
    """Mark shipment as shipped."""
    simulate_latency(50, 100)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get order_id for the shipment
    cursor.execute("SELECT order_id FROM shipments WHERE id = %s", (shipment_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Shipment not found'}), 404

    order_id = row[0]

    cursor.execute("UPDATE shipments SET status = %s WHERE id = %s", ('SHIPPED', shipment_id))
    conn.commit()
    cursor.close()
    conn.close()

    # Send update to Kafka
    try:
        send_to_kafka('shipments', f"{shipment_id}:{order_id}:SHIPPED")
        send_to_kafka('order-updates', f"{order_id}:SHIPPED")
    except Exception as e:
        logger.error(f"Failed to send to Kafka: {e}")

    return jsonify({'id': shipment_id, 'status': 'SHIPPED'})


@app.route('/api/shipments/<shipment_id>/deliver', methods=['PUT'])
def deliver_shipment(shipment_id):
    """Mark shipment as delivered."""
    simulate_latency(50, 100)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get order_id for the shipment
    cursor.execute("SELECT order_id FROM shipments WHERE id = %s", (shipment_id,))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({'error': 'Shipment not found'}), 404

    order_id = row[0]

    cursor.execute("UPDATE shipments SET status = %s WHERE id = %s", ('DELIVERED', shipment_id))
    conn.commit()
    cursor.close()
    conn.close()

    # Send update to Kafka
    try:
        send_to_kafka('shipments', f"{shipment_id}:{order_id}:DELIVERED")
        send_to_kafka('order-updates', f"{order_id}:DELIVERED")
    except Exception as e:
        logger.error(f"Failed to send to Kafka: {e}")

    return jsonify({'id': shipment_id, 'status': 'DELIVERED'})


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

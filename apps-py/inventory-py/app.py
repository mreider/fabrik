"""
Inventory Service - Python version
Kafka consumer/producer for inventory management.
"""
import os
import sys
import logging
import random
import threading
from flask import Flask, jsonify

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.chaos import apply_msg_slowdown, apply_db_slowdown
from common.db import get_db_connection, init_db_tables

from kafka import KafkaConsumer, KafkaProducer

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


@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Get current inventory levels."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT product_name, quantity FROM inventory ORDER BY product_name")
    inventory = []
    for row in cursor.fetchall():
        inventory.append({
            'product': row[0],
            'quantity': row[1]
        })
    cursor.close()
    conn.close()
    return jsonify(inventory)


def process_order(order_id: str):
    """Process order - reserve inventory."""
    logger.info(f"Processing order for inventory: {order_id}")

    # Pattern 1: Message processing slowdown
    apply_msg_slowdown(f"order {order_id[:8]}")

    # Pattern 2: DB slowdown
    conn = None
    try:
        conn = get_db_connection()
        apply_db_slowdown(conn, f"order {order_id[:8]}")

        cursor = conn.cursor()

        # Get order details
        cursor.execute("SELECT product, quantity FROM orders WHERE id = %s", (order_id,))
        row = cursor.fetchone()

        if row:
            product = row[0]
            quantity = row[1]

            # Check/update inventory
            cursor.execute("SELECT quantity FROM inventory WHERE product_name = %s", (product,))
            inv_row = cursor.fetchone()

            if inv_row and inv_row[0] >= quantity:
                # Reserve inventory
                cursor.execute(
                    "UPDATE inventory SET quantity = quantity - %s WHERE product_name = %s",
                    (quantity, product)
                )
                conn.commit()
                logger.info(f"Inventory reserved for order {order_id}: {product} x {quantity}")

                # Send confirmation to Kafka
                try:
                    send_to_kafka('inventory-reserved', f"{order_id}:RESERVED")
                    send_to_kafka('order-updates', f"{order_id}:INVENTORY_RESERVED")
                except Exception as e:
                    logger.error(f"Failed to send to Kafka: {e}")
            else:
                logger.warning(f"Insufficient inventory for order {order_id}: {product}")
                try:
                    send_to_kafka('order-updates', f"{order_id}:OUT_OF_STOCK")
                except Exception as e:
                    logger.error(f"Failed to send to Kafka: {e}")
        else:
            logger.error(f"Order not found: {order_id}")

        cursor.close()
    except Exception as e:
        logger.error(f"Error processing order {order_id}: {e}")
    finally:
        if conn:
            conn.close()


def kafka_consumer_thread():
    """Background thread for Kafka consumption."""
    bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

    # Wait for Kafka to be ready
    import time
    max_retries = 60
    for i in range(max_retries):
        try:
            consumer = KafkaConsumer(
                'orders',
                bootstrap_servers=bootstrap_servers,
                group_id='inventory-group',
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                value_deserializer=lambda m: m.decode('utf-8')
            )
            logger.info("Kafka consumer connected successfully")
            break
        except Exception as e:
            logger.warning(f"Waiting for Kafka (attempt {i+1}/{max_retries}): {e}")
            time.sleep(2)
    else:
        logger.error("Failed to connect to Kafka after max retries")
        return

    # Consume messages
    for message in consumer:
        try:
            order_id = message.value
            logger.debug(f"Received order from Kafka: {order_id}")
            process_order(order_id)
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def seed_inventory(conn):
    """Seed initial inventory data."""
    cursor = conn.cursor()

    products = [
        ('Widget A', 100),
        ('Widget B', 50),
        ('Widget C', 25),
        ('Gadget X', 10),
        ('Gadget Y', 5),
    ]

    for product, quantity in products:
        cursor.execute("""
            INSERT INTO inventory (product_name, quantity)
            VALUES (%s, %s)
            ON CONFLICT (product_name) DO UPDATE SET quantity = EXCLUDED.quantity
        """, (product, quantity))

    conn.commit()
    cursor.close()
    logger.info("Inventory seeded")


def initialize():
    """Initialize database and start Kafka consumer."""
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            init_db_tables(conn)
            seed_inventory(conn)
            conn.close()
            logger.info("Database initialized successfully")
            break
        except Exception as e:
            logger.warning(f"Database not ready (attempt {i+1}/{max_retries}): {e}")
            import time
            time.sleep(2)
    else:
        logger.error("Failed to initialize database after max retries")

    # Start Kafka consumer in background thread
    consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    consumer_thread.start()
    logger.info("Kafka consumer thread started")


# Initialize on import for gunicorn
initialize()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8082, debug=True)

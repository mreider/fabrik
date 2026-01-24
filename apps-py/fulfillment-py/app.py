"""
Fulfillment Service - Python version
Kafka consumer for fraud detection.
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

from kafka import KafkaConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/health', methods=['GET'])
@app.route('/actuator/health', methods=['GET'])
def health():
    return jsonify({'status': 'UP'})


def process_order(order_id: str):
    """Process order - fraud detection."""
    logger.info(f"Processing order for fraud check: {order_id}")

    # Pattern 1: Message processing slowdown
    apply_msg_slowdown(f"order {order_id[:8]}")

    # Pattern 2: DB slowdown
    conn = None
    try:
        conn = get_db_connection()
        apply_db_slowdown(conn, f"order {order_id[:8]}")

        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM orders WHERE id = %s", (order_id,))
        row = cursor.fetchone()

        if row:
            # Simulate fraud check - 10% fraud rate
            if random.random() > 0.9:
                new_status = 'FRAUD_DETECTED'
                logger.warning(f"Fraud detected for order: {order_id}")
            else:
                new_status = 'FRAUD_CHECK_PASSED'
                logger.info(f"Fraud check passed for order: {order_id}")

            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
            conn.commit()
        else:
            logger.error(f"Order not found: {order_id}")

        cursor.close()
    except Exception as e:
        logger.error(f"Error processing order {order_id}: {e}")
    finally:
        if conn:
            conn.close()


def process_order_update(message: str):
    """Process order update message."""
    parts = message.split(':')
    if len(parts) < 2:
        logger.warning(f"Invalid order update message format: {message}")
        return

    order_id = parts[0]
    new_status = parts[1]
    logger.info(f"Processing order update: {order_id} -> {new_status}")

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Simulate processing delay
        import time
        time.sleep(0.02 + random.random() * 0.04)

        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        row = cursor.fetchone()

        if row:
            previous_status = row[0]
            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (new_status, order_id))
            conn.commit()
            logger.info(f"Order {order_id} status updated: {previous_status} -> {new_status}")

        cursor.close()
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {e}")
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
                'orders', 'order-updates',
                bootstrap_servers=bootstrap_servers,
                group_id='fulfillment-group',
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
            topic = message.topic
            value = message.value
            logger.debug(f"Received message from {topic}: {value}")

            if topic == 'orders':
                process_order(value)
            elif topic == 'order-updates':
                process_order_update(value)
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def initialize():
    """Initialize database and start Kafka consumer."""
    max_retries = 30
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            init_db_tables(conn)
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
    app.run(host='0.0.0.0', port=8080, debug=True)

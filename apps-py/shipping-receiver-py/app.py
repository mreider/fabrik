"""
Shipping Receiver Service - Python version
Kafka consumer that calls shipping-processor REST API.
"""
import os
import sys
import logging
import threading
import requests
from flask import Flask, jsonify

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.chaos import apply_msg_slowdown, apply_slowdown

from kafka import KafkaConsumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Shipping processor service URL
SHIPPING_PROCESSOR_URL = os.environ.get('SHIPPING_PROCESSOR_URL', 'http://shipping-processor:8080')


@app.route('/health', methods=['GET'])
@app.route('/actuator/health', methods=['GET'])
def health():
    return jsonify({'status': 'UP'})


def process_inventory_reserved(message: str):
    """Process inventory-reserved message - create shipment."""
    parts = message.split(':')
    if len(parts) < 2:
        logger.warning(f"Invalid inventory-reserved message format: {message}")
        return

    order_id = parts[0]
    status = parts[1]

    if status != 'RESERVED':
        logger.debug(f"Ignoring non-RESERVED status: {status}")
        return

    logger.info(f"Processing inventory reserved for order: {order_id}")

    # Pattern 1: Message processing slowdown
    apply_msg_slowdown(f"order {order_id[:8]}")

    # Pattern 2: Service slowdown
    apply_slowdown(f"order {order_id[:8]}")

    # Call shipping-processor to create shipment
    try:
        response = requests.post(
            f"{SHIPPING_PROCESSOR_URL}/api/shipments",
            json={'orderId': order_id},
            timeout=60
        )
        response.raise_for_status()
        shipment = response.json()
        logger.info(f"Shipment created: {shipment.get('id')} for order {order_id}")
    except requests.exceptions.Timeout:
        logger.error(f"Shipping processor timeout for order {order_id}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create shipment for order {order_id}: {e}")


def kafka_consumer_thread():
    """Background thread for Kafka consumption."""
    bootstrap_servers = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

    # Wait for Kafka to be ready
    import time
    max_retries = 60
    for i in range(max_retries):
        try:
            consumer = KafkaConsumer(
                'inventory-reserved',
                bootstrap_servers=bootstrap_servers,
                group_id='shipping-receiver-group',
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
            value = message.value
            logger.debug(f"Received message from inventory-reserved: {value}")
            process_inventory_reserved(value)
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def initialize():
    """Start Kafka consumer."""
    # Start Kafka consumer in background thread
    consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    consumer_thread.start()
    logger.info("Kafka consumer thread started")


# Initialize on import for gunicorn
initialize()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8083, debug=True)

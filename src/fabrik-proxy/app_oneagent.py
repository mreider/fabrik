import os
import requests
import logging
import json
import random
import threading
import time
import pika
from flask import Flask, jsonify, request

app = Flask("fabrik-proxy-oneagent")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FABRIK_SERVICE_URL = os.getenv('FABRIK_SERVICE_URL', 'http://fabrik-service:8080')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'fabrik')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'fabrik123')

# Global flag for message consumer
consumer_running = False

def get_rabbitmq_connection():
    """Get RabbitMQ connection"""
    try:
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
        parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
        return None

def process_message(ch, method, properties, body):
    """Process received message"""
    try:
        # Random chance of message processing failure (5%)
        if random.random() < 0.05:
            logger.error("Simulated message processing failure")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

        message_data = json.loads(body)
        logger.info(f"Processing message: {message_data.get('id', 'unknown')} from queue {method.routing_key}")

        # Simulate processing time
        import time
        time.sleep(random.uniform(0.1, 0.5))

        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Message processed successfully: {message_data.get('id', 'unknown')}")

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_message_consumer():
    """Start consuming messages from RabbitMQ queues"""
    global consumer_running
    consumer_running = True

    logger.info("Starting message consumer...")

    # Wait a bit for RabbitMQ to be ready
    import time
    time.sleep(10)

    while consumer_running:
        try:
            connection = get_rabbitmq_connection()
            if not connection:
                logger.error("Could not connect to RabbitMQ, retrying in 10 seconds...")
                time.sleep(10)
                continue

            channel = connection.channel()

            # Declare queues to consume from
            queues = ['order_processing', 'user_notifications', 'inventory_updates']
            for queue_name in queues:
                channel.queue_declare(queue=queue_name, durable=True)
                channel.basic_consume(queue=queue_name, on_message_callback=process_message)

            logger.info("Message consumer started, waiting for messages...")
            channel.start_consuming()

        except Exception as e:
            logger.error(f"Error in message consumer: {str(e)}")
            time.sleep(5)
        finally:
            try:
                connection.close()
            except:
                pass

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "fabrik-proxy",
        "instrumentation": "oneagent",
        "message_consumer_running": consumer_running
    })

@app.route('/api/proxy', methods=['GET', 'POST'])
def proxy_request():
    """Proxy requests to fabrik-service"""
    logger.info(f"Received request at /api/proxy endpoint")

    try:
        # Extract client information from request
        client_data = {}
        if request.method == 'POST' and request.is_json:
            client_data = request.get_json() or {}

        # Propagate headers and add new ones
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': request.headers.get('User-Agent', 'Fabrik-Proxy/1.0'),
            'X-Forwarded-By': 'fabrik-proxy',
            'X-Client-ID': request.headers.get('X-Client-ID', f'proxy-{random.randint(1000, 9999)}'),
            'X-Request-Source': request.headers.get('X-Request-Source', 'proxy'),
            'X-Correlation-ID': request.headers.get('X-Correlation-ID', f'proxy-{int(time.time())}-{random.randint(100, 999)}')
        }

        # Prepare payload with client info and proxy metadata
        payload = {
            'client_info': client_data.get('client_info', {}),
            'proxy_info': {
                'service': 'fabrik-proxy',
                'forwarded_from': request.remote_addr,
                'original_headers': dict(request.headers)
            },
            'request_data': client_data.get('request_data', {})
        }
        payload['request_data']['proxied_at'] = time.time()

        # Call fabrik-service
        upstream_url = f"{FABRIK_SERVICE_URL}/api/process"
        logger.info(f"Making request to: {upstream_url}")

        response = requests.post(upstream_url, json=payload, headers=headers, timeout=10)

        logger.info(f"Received response from fabrik-service: {response.status_code}")

        if response.status_code == 200:
            logger.info(f"Successfully proxied request to fabrik-service")
            return jsonify({
                "status": "success",
                "proxy": "fabrik-proxy",
                "instrumentation": "oneagent",
                "upstream_response": response.json()
            })
        else:
            logger.error(f"Upstream service returned {response.status_code}: {response.text}")
            return jsonify({
                "status": "error",
                "proxy": "fabrik-proxy",
                "instrumentation": "oneagent",
                "error": f"Upstream service returned {response.status_code}",
                "upstream_response": response.text
            }), response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception when calling {upstream_url}: {str(e)}")
        return jsonify({
            "status": "error",
            "proxy": "fabrik-proxy",
            "instrumentation": "oneagent",
            "error": str(e),
            "upstream_url": upstream_url
        }), 500

def check_fabrik_service_health():
    """Check if fabrik-service is reachable"""
    try:
        logger.info(f"Checking fabrik-service health at {FABRIK_SERVICE_URL}/health")
        response = requests.get(f"{FABRIK_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("fabrik-service is healthy and reachable")
            return True
        else:
            logger.warning(f"fabrik-service health check returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"fabrik-service health check failed: {str(e)}")
        return False

if __name__ == '__main__':
    logger.info("Starting fabrik-proxy with OneAgent instrumentation")
    logger.info(f"fabrik-service URL: {FABRIK_SERVICE_URL}")

    # Check fabrik-service health
    check_fabrik_service_health()

    # Start message consumer in background
    logger.info("Starting message consumer in background thread")
    consumer_thread = threading.Thread(target=start_message_consumer, daemon=True)
    consumer_thread.start()

    logger.info("fabrik-proxy is ready to receive requests and process messages")
    app.run(host='0.0.0.0', port=8080, debug=False)
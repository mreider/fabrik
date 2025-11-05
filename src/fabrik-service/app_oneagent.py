import os
import time
import random
import json
import logging
import requests
import redis
import mysql.connector
import pika
from flask import Flask, jsonify

app = Flask(__name__)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_USER = os.getenv('MYSQL_USER', 'fabrik')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'fabrik123')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'fabrik')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'fabrik')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'fabrik123')

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_mysql_connection():
    """Get MySQL database connection with retry logic"""
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            autocommit=True
        )
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to MySQL: {str(e)}")
        return None

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

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "fabrik-service",
        "instrumentation": "oneagent"
    })

@app.route('/api/process')
def process_request():
    """Main processing endpoint - returns 200, some 500s, writes to Redis"""
    logger.info("Received request at /api/process endpoint")

    # Simulate some processing time
    processing_time = random.uniform(0.05, 0.3)
    time.sleep(processing_time)

    # Randomly return 500 errors (20% chance)
    if random.random() < 0.2:
        logger.error("Random server error occurred during processing")
        return jsonify({
            "status": "error",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "error": "Random server error"
        }), 500

    # Write to Redis occasionally (30% chance)
    redis_data = None
    if random.random() < 0.3:
        try:
            redis_data = write_to_redis()
        except Exception as e:
            logger.error(f"Redis write failed: {str(e)}")

    # Database operation occasionally (50% chance)
    db_data = None
    if random.random() < 0.5:
        try:
            db_data = perform_database_operation()
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")

    # Publish message occasionally (40% chance)
    message_data = None
    if random.random() < 0.4:
        try:
            message_data = publish_message()
        except Exception as e:
            logger.error(f"Message publishing failed: {str(e)}")

    # Make external HTTP request occasionally (30% chance)
    external_request_data = None
    if random.random() < 0.3:
        try:
            external_request_data = make_external_request()
        except Exception as e:
            logger.error(f"External request failed: {str(e)}")

    # Successful response
    response_data = {
        "status": "success",
        "service": "fabrik-service",
        "instrumentation": "oneagent",
        "timestamp": time.time(),
        "processing_time_ms": round(processing_time * 1000, 2),
        "request_id": f"req_{random.randint(1000, 9999)}"
    }

    if redis_data:
        response_data["redis_operation"] = redis_data

    if db_data:
        response_data["database_operation"] = db_data

    if message_data:
        response_data["message_published"] = message_data

    if external_request_data:
        response_data["external_request"] = external_request_data

    logger.info(f"Successfully processed request {response_data['request_id']}")
    return jsonify(response_data)

def perform_database_operation():
    """Perform database operations with random queries and failures"""
    connection = get_mysql_connection()
    if not connection:
        raise Exception("Could not connect to database")

    try:
        cursor = connection.cursor()

        # Random chance of database failure (10%)
        if random.random() < 0.1:
            cursor.close()
            connection.close()
            raise Exception("Simulated database query failure")

        # Random operation
        operation = random.choice(['select_users', 'select_orders', 'insert_order'])

        if operation == 'select_users':
            cursor.execute("SELECT id, username, email FROM users ORDER BY RAND() LIMIT 5")
            results = cursor.fetchall()
            logger.info(f"Database: Selected {len(results)} users")
            return {
                "operation": "select_users",
                "count": len(results),
                "table": "users"
            }

        elif operation == 'select_orders':
            cursor.execute("""
                SELECT o.id, o.product_name, o.quantity, u.username
                FROM orders o
                JOIN users u ON o.user_id = u.id
                ORDER BY o.created_at DESC LIMIT 10
            """)
            results = cursor.fetchall()
            logger.info(f"Database: Selected {len(results)} orders")
            return {
                "operation": "select_orders",
                "count": len(results),
                "table": "orders"
            }

        elif operation == 'insert_order':
            user_id = random.randint(1, 3)
            products = ['Widget A', 'Widget B', 'Widget C', 'Gadget X', 'Gadget Y']
            product = random.choice(products)
            quantity = random.randint(1, 5)
            amount = round(random.uniform(10.0, 100.0), 2)

            cursor.execute("""
                INSERT INTO orders (user_id, product_name, quantity, total_amount)
                VALUES (%s, %s, %s, %s)
            """, (user_id, product, quantity, amount))

            order_id = cursor.lastrowid
            logger.info(f"Database: Inserted order {order_id}")
            return {
                "operation": "insert_order",
                "order_id": order_id,
                "product": product,
                "table": "orders"
            }

    finally:
        cursor.close()
        connection.close()

def publish_message():
    """Publish message to RabbitMQ queue with failures"""
    connection = get_rabbitmq_connection()
    if not connection:
        raise Exception("Could not connect to RabbitMQ")

    try:
        channel = connection.channel()

        # Random chance of messaging failure (8%)
        if random.random() < 0.08:
            channel.close()
            connection.close()
            raise Exception("Simulated message publishing failure")

        # Declare queues
        queue_name = random.choice(['order_processing', 'user_notifications', 'inventory_updates'])
        channel.queue_declare(queue=queue_name, durable=True)

        # Create message
        message_data = {
            "id": f"msg_{random.randint(1000, 9999)}",
            "timestamp": time.time(),
            "type": random.choice(['order_created', 'user_updated', 'inventory_changed']),
            "data": {"demo": "data", "value": random.randint(1, 100)}
        }

        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(message_data),
            properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
        )

        logger.info(f"Message published to queue {queue_name}: {message_data['id']}")

        return {
            "queue": queue_name,
            "message_id": message_data["id"],
            "type": message_data["type"]
        }

    finally:
        channel.close()
        connection.close()

def make_external_request():
    """Make external HTTP requests to httpstatus testing endpoints"""
    # List of external endpoints to call
    endpoints = [
        "https://tools-httpstatus.pickup-services.com/200",
        "https://tools-httpstatus.pickup-services.com/random/200,201,500-504",
        "https://tools-httpstatus.pickup-services.com/201",
        "https://tools-httpstatus.pickup-services.com/500",
        "https://tools-httpstatus.pickup-services.com/503"
    ]

    # Randomly select an endpoint
    endpoint = random.choice(endpoints)

    try:
        logger.info(f"Making external request to: {endpoint}")
        response = requests.get(endpoint, timeout=5)

        logger.info(f"External request completed: {endpoint} -> {response.status_code}")

        return {
            "url": endpoint,
            "status_code": response.status_code,
            "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
            "success": 200 <= response.status_code < 300
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"External request failed: {endpoint} -> {str(e)}")

        return {
            "url": endpoint,
            "status_code": "error",
            "error": str(e),
            "success": False
        }

def write_to_redis():
    """Write some data to Redis"""
    key = f"fabrik:data:{random.randint(1, 1000)}"
    value = {
        "timestamp": time.time(),
        "data": f"sample_data_{random.randint(1, 100)}",
        "counter": random.randint(1, 1000)
    }

    redis_client.setex(key, 300, json.dumps(value))  # Expire after 5 minutes

    logger.info(f"Wrote data to Redis key: {key}")
    return {"key": key, "value": value, "ttl": 300}

@app.route('/api/external')
def external_request_endpoint():
    """Dedicated endpoint for making external HTTP requests"""
    logger.info("Received request at /api/external endpoint")

    try:
        external_request_data = make_external_request()

        return jsonify({
            "status": "success",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "timestamp": time.time(),
            "external_request": external_request_data
        })

    except Exception as e:
        logger.error(f"External request endpoint failed: {str(e)}")

        return jsonify({
            "status": "error",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "error": str(e)
        }), 500

@app.route('/api/redis/stats')
def redis_stats():
    """Get Redis statistics"""
    try:
        info = redis_client.info()
        keys_count = redis_client.dbsize()

        return jsonify({
            "status": "success",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "redis_stats": {
                "keys_count": keys_count,
                "memory_used_bytes": info.get('used_memory', 0),
                "memory_used_human": info.get('used_memory_human', 'unknown'),
                "connected_clients": info.get('connected_clients', 0),
                "uptime_seconds": info.get('uptime_in_seconds', 0)
            }
        })
    except Exception as e:
        logger.error(f"Failed to get Redis stats: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "error": str(e)
        }), 500

@app.route('/api/redis/cleanup')
def redis_cleanup():
    """Clean up Redis to avoid disk growth"""
    try:
        # Get all fabrik keys
        keys = redis_client.keys("fabrik:*")
        deleted_count = 0

        if keys:
            deleted_count = redis_client.delete(*keys)

        logger.info(f"Redis cleanup completed. Deleted {deleted_count} keys")
        return jsonify({
            "status": "success",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "cleanup_result": {
                "keys_deleted": deleted_count,
                "keys_found": len(keys)
            }
        })
    except Exception as e:
        logger.error(f"Redis cleanup failed: {str(e)}")
        return jsonify({
            "status": "error",
            "service": "fabrik-service",
            "instrumentation": "oneagent",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    logger.info("Starting fabrik-service with OneAgent instrumentation")
    logger.info(f"Redis connection: {REDIS_HOST}:{REDIS_PORT}")
    logger.info("fabrik-service is ready to receive requests")
    app.run(host='0.0.0.0', port=8080, debug=False)
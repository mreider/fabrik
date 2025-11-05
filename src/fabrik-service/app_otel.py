import os
import time
import random
import json
import logging
import requests
import redis
import mysql.connector
import pika
from flask import Flask, jsonify, request
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.mysql import MySQLInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import Status, StatusCode

app = Flask("fabrik-service-otel")

# Configuration
# OpenTelemetry will use OTEL_EXPORTER_OTLP_ENDPOINT automatically
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql')
MYSQL_USER = os.getenv('MYSQL_USER', 'fabrik')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'fabrik123')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'fabrik')
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'fabrik')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'fabrik123')

# Initialize OpenTelemetry
def init_otel():
    print(f"[OTEL INIT] Starting OpenTelemetry initialization for fabrik-service")
    print(f"[OTEL INIT] Using OTEL_EXPORTER_OTLP_ENDPOINT environment variable for automatic configuration")
    # OpenTelemetry will handle authentication automatically via OTEL_EXPORTER_OTLP_ENDPOINT
    
    # Import resource for proper service identification
    from opentelemetry.sdk.resources import Resource
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "fabrik-service",
        "service.version": "1.0.0",
        "service.namespace": "fabrik"
    })
    
    try:
        # Traces
        print(f"[OTEL INIT] Setting up trace exporter using OTEL_EXPORTER_OTLP_ENDPOINT")
        trace_exporter = OTLPSpanExporter()
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(trace_exporter)
        )
        print(f"[OTEL INIT] Trace exporter configured successfully")
        
        # Metrics
        print(f"[OTEL INIT] Setting up metric exporter using OTEL_EXPORTER_OTLP_ENDPOINT")
        metric_exporter = OTLPMetricExporter()
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=10000
        )
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        print(f"[OTEL INIT] Metric exporter configured successfully")
        
        # Logs
        print(f"[OTEL INIT] Setting up log exporter using OTEL_EXPORTER_OTLP_ENDPOINT")
        log_exporter = OTLPLogExporter()
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(log_exporter)
        )
        print(f"[OTEL INIT] Log exporter configured successfully")
        
        # Configure logging
        handler = LoggingHandler(logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        print(f"[OTEL INIT] OpenTelemetry initialization completed successfully")
        
    except Exception as e:
        print(f"[OTEL INIT] ERROR: Failed to initialize OpenTelemetry: {str(e)}")
        raise

# Initialize OTEL
init_otel()

# Set up console logging as well
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Get tracer and meter
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create custom metrics
request_counter = meter.create_counter(
    "fabrik_requests_total",
    description="Total number of requests processed"
)

error_counter = meter.create_counter(
    "fabrik_errors_total", 
    description="Total number of errors"
)

redis_operations_counter = meter.create_counter(
    "fabrik_redis_operations_total",
    description="Total number of Redis operations"
)

external_requests_counter = meter.create_counter(
    "fabrik_external_requests_total",
    description="Total number of external HTTP requests"
)

# Instrument Flask, Redis, MySQL, Pika, and Requests
FlaskInstrumentor().instrument_app(app)
RedisInstrumentor().instrument()
MySQLInstrumentor().instrument()
PikaInstrumentor().instrument()
from opentelemetry.instrumentation.requests import RequestsInstrumentor
RequestsInstrumentor().instrument()

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

# Logger
logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "fabrik-service"})

@app.route('/api/process', methods=['GET', 'POST'])
def process_request():
    """Main processing endpoint - returns 200, some 500s, writes to Redis"""

    # Extract client and proxy information from POST request
    client_info = {}
    proxy_info = {}
    request_data = {}

    if request.method == 'POST' and request.is_json:
        payload = request.get_json() or {}
        client_info = payload.get('client_info', {})
        proxy_info = payload.get('proxy_info', {})
        request_data = payload.get('request_data', {})

        logger.info(f"Received POST request at /api/process endpoint from client: {client_info.get('client_id', 'unknown')}")

        # Log client information
        if client_info:
            logger.info(f"Client info: {client_info.get('user_agent', 'unknown')} from {client_info.get('request_source', 'unknown')}")

        # Log proxy information
        if proxy_info:
            logger.info(f"Proxied by: {proxy_info.get('service', 'unknown')} from {proxy_info.get('forwarded_from', 'unknown')}")
    else:
        logger.info("Received GET request at /api/process endpoint")

    request_counter.add(1, {"endpoint": "/api/process"})

    with tracer.start_as_current_span("process_request", kind=trace.SpanKind.SERVER) as span:
        span.set_attribute("service.name", "fabrik-service")
        span.set_attribute("operation", "process_request")

        # Add client and proxy info to span
        if client_info:
            span.set_attribute("client.id", client_info.get('client_id', 'unknown'))
            span.set_attribute("client.user_agent", client_info.get('user_agent', 'unknown'))
            span.set_attribute("client.request_source", client_info.get('request_source', 'unknown'))

        if proxy_info:
            span.set_attribute("proxy.service", proxy_info.get('service', 'unknown'))
            span.set_attribute("proxy.forwarded_from", proxy_info.get('forwarded_from', 'unknown'))
        
        # Simulate some processing time
        processing_time = random.uniform(0.05, 0.3)
        time.sleep(processing_time)
        span.set_attribute("processing.time_ms", processing_time * 1000)
        
        # Randomly return 500 errors (20% chance)
        if random.random() < 0.2:
            error_counter.add(1, {"type": "random_error"})
            span.set_attribute("error", True)
            span.set_attribute("error.type", "random_server_error")
            logger.error("Random server error occurred during processing")
            return jsonify({
                "status": "error",
                "service": "fabrik-service",
                "error": "Random server error"
            }), 500
        
        # Write to Redis occasionally (30% chance)
        redis_data = None
        if random.random() < 0.3:
            try:
                redis_data = write_to_redis()
                span.set_attribute("redis.write", True)
                span.set_attribute("redis.key", redis_data["key"])
            except Exception as e:
                logger.error(f"Redis write failed: {str(e)}")
                span.set_attribute("redis.error", True)
                span.set_attribute("redis.error.message", str(e))

        # Database operation occasionally (50% chance)
        db_data = None
        if random.random() < 0.5:
            try:
                db_data = perform_database_operation()
                span.set_attribute("db.operation", True)
                span.set_attribute("db.operation.type", db_data["operation"])
                span.set_attribute("db.collection.name", db_data["table"])
            except Exception as e:
                logger.error(f"Database operation failed: {str(e)}")
                span.set_attribute("db.error", True)
                span.set_attribute("db.error.message", str(e))

        # Publish message occasionally (40% chance)
        message_data = None
        if random.random() < 0.4:
            try:
                message_data = publish_message()
                span.set_attribute("messaging.operation", True)
                span.set_attribute("messaging.destination.name", message_data["queue"])
                span.set_attribute("messaging.operation.type", "publish")
            except Exception as e:
                logger.error(f"Message publishing failed: {str(e)}")
                span.set_attribute("messaging.error", True)
                span.set_attribute("messaging.error.message", str(e))

        # Make external HTTP request occasionally (30% chance)
        external_request_data = None
        if random.random() < 0.3:
            try:
                external_request_data = make_external_request()
                span.set_attribute("external.request", True)
                span.set_attribute("external.url", external_request_data["url"])
                span.set_attribute("external.status_code", external_request_data["status_code"])
            except Exception as e:
                logger.error(f"External request failed: {str(e)}")
                span.set_attribute("external.error", True)
                span.set_attribute("external.error.message", str(e))
        
        # Successful response
        response_data = {
            "status": "success",
            "service": "fabrik-service",
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

        # Include client and proxy information in response
        if client_info:
            response_data["received_client_info"] = client_info

        if proxy_info:
            response_data["received_proxy_info"] = proxy_info

        if request_data:
            response_data["received_request_data"] = request_data

        logger.info(f"Successfully processed request {response_data['request_id']}")
        return jsonify(response_data)

def perform_database_operation():
    """Perform database operations with OpenTelemetry semantic attributes"""
    with tracer.start_as_current_span("database_operation", kind=trace.SpanKind.CLIENT) as span:
        connection = get_mysql_connection()
        if not connection:
            span.set_status(Status(StatusCode.ERROR, "Could not connect to database"))
            raise Exception("Could not connect to database")

        try:
            cursor = connection.cursor()

            # Set database semantic attributes
            span.set_attribute(SpanAttributes.DB_SYSTEM, "mysql")
            span.set_attribute(SpanAttributes.DB_NAME, MYSQL_DATABASE)
            span.set_attribute("server.address", MYSQL_HOST)
            span.set_attribute("server.port", 3306)
            span.set_attribute(SpanAttributes.DB_USER, MYSQL_USER)

            # Random chance of database failure (10%)
            if random.random() < 0.1:
                cursor.close()
                connection.close()
                span.set_status(Status(StatusCode.ERROR, "Simulated database query failure"))
                raise Exception("Simulated database query failure")

            # Random operation
            operation = random.choice(['select_users', 'select_orders', 'insert_order'])
            span.set_attribute(SpanAttributes.DB_OPERATION, operation)

            if operation == 'select_users':
                sql_query = "SELECT id, username, email FROM users ORDER BY RAND() LIMIT 5"
                span.set_attribute(SpanAttributes.DB_STATEMENT, sql_query)
                span.set_attribute("db.collection.name", "users")

                cursor.execute(sql_query)
                results = cursor.fetchall()
                logger.info(f"Database: Selected {len(results)} users")

                span.set_attribute("db.rows_affected", len(results))
                span.set_status(Status(StatusCode.OK))

                return {
                    "operation": "select_users",
                    "count": len(results),
                    "table": "users"
                }

            elif operation == 'select_orders':
                sql_query = """
                    SELECT o.id, o.product_name, o.quantity, u.username
                    FROM orders o
                    JOIN users u ON o.user_id = u.id
                    ORDER BY o.created_at DESC LIMIT 10
                """
                span.set_attribute(SpanAttributes.DB_STATEMENT, sql_query)
                span.set_attribute("db.collection.name", "orders")

                cursor.execute(sql_query)
                results = cursor.fetchall()
                logger.info(f"Database: Selected {len(results)} orders")

                span.set_attribute("db.rows_affected", len(results))
                span.set_status(Status(StatusCode.OK))

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

                sql_query = """
                    INSERT INTO orders (user_id, product_name, quantity, total_amount)
                    VALUES (%s, %s, %s, %s)
                """
                span.set_attribute(SpanAttributes.DB_STATEMENT, sql_query)
                span.set_attribute("db.collection.name", "orders")

                cursor.execute(sql_query, (user_id, product, quantity, amount))
                order_id = cursor.lastrowid
                logger.info(f"Database: Inserted order {order_id}")

                span.set_attribute("db.rows_affected", 1)
                span.set_attribute("db.record_id", order_id)
                span.set_status(Status(StatusCode.OK))

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
    """Publish message to RabbitMQ with OpenTelemetry semantic attributes"""
    with tracer.start_as_current_span("message_publish", kind=trace.SpanKind.PRODUCER) as span:
        connection = get_rabbitmq_connection()
        if not connection:
            span.set_status(Status(StatusCode.ERROR, "Could not connect to RabbitMQ"))
            raise Exception("Could not connect to RabbitMQ")

        try:
            channel = connection.channel()

            # Random chance of messaging failure (8%)
            if random.random() < 0.08:
                channel.close()
                connection.close()
                span.set_status(Status(StatusCode.ERROR, "Simulated message publishing failure"))
                raise Exception("Simulated message publishing failure")

            # Declare queues
            queue_name = random.choice(['order_processing', 'user_notifications', 'inventory_updates'])
            channel.queue_declare(queue=queue_name, durable=True)

            # Set messaging semantic attributes
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination.name", queue_name)
            span.set_attribute("messaging.destination.kind", "queue")
            span.set_attribute("messaging.operation.type", "publish")
            span.set_attribute("server.address", RABBITMQ_HOST)
            span.set_attribute("server.port", 5672)

            # Create message
            message_data = {
                "id": f"msg_{random.randint(1000, 9999)}",
                "timestamp": time.time(),
                "type": random.choice(['order_created', 'user_updated', 'inventory_changed']),
                "data": {"demo": "data", "value": random.randint(1, 100)}
            }

            # Set message attributes
            span.set_attribute("messaging.message.id", message_data["id"])
            span.set_attribute("messaging.message.payload_size_bytes", len(json.dumps(message_data)))

            # Publish message
            channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message_data),
                properties=pika.BasicProperties(delivery_mode=2)  # Make message persistent
            )

            logger.info(f"Message published to queue {queue_name}: {message_data['id']}")
            span.set_status(Status(StatusCode.OK))

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
    with tracer.start_as_current_span("external_request", kind=trace.SpanKind.CLIENT) as span:
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
            span.set_attribute("http.url", endpoint)
            span.set_attribute("http.method", "GET")
            
            response = requests.get(endpoint, timeout=5)
            
            external_requests_counter.add(1, {
                "endpoint": endpoint,
                "status_code": str(response.status_code)
            })
            
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_size", len(response.content))
            
            logger.info(f"External request completed: {endpoint} -> {response.status_code}")
            
            return {
                "url": endpoint,
                "status_code": response.status_code,
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "success": 200 <= response.status_code < 300
            }
            
        except requests.exceptions.RequestException as e:
            external_requests_counter.add(1, {
                "endpoint": endpoint,
                "status_code": "error"
            })
            
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            
            logger.error(f"External request failed: {endpoint} -> {str(e)}")
            
            return {
                "url": endpoint,
                "status_code": "error",
                "error": str(e),
                "success": False
            }

def write_to_redis():
    """Write some data to Redis"""
    with tracer.start_as_current_span("redis_write", kind=trace.SpanKind.CLIENT) as span:
        key = f"fabrik:data:{random.randint(1, 1000)}"
        value = {
            "timestamp": time.time(),
            "data": f"sample_data_{random.randint(1, 100)}",
            "counter": random.randint(1, 1000)
        }
        
        redis_client.setex(key, 300, json.dumps(value))  # Expire after 5 minutes
        redis_operations_counter.add(1, {"operation": "write"})
        
        span.set_attribute("redis.key", key)
        span.set_attribute("redis.ttl", 300)
        
        logger.info(f"Wrote data to Redis key: {key}")
        return {"key": key, "value": value, "ttl": 300}

@app.route('/api/external')
def external_request_endpoint():
    """Dedicated endpoint for making external HTTP requests"""
    logger.info("Received request at /api/external endpoint")
    request_counter.add(1, {"endpoint": "/api/external"})
    
    with tracer.start_as_current_span("external_request_endpoint", kind=trace.SpanKind.SERVER) as span:
        span.set_attribute("service.name", "fabrik-service")
        span.set_attribute("operation", "external_request_endpoint")
        
        try:
            external_request_data = make_external_request()
            
            return jsonify({
                "status": "success",
                "service": "fabrik-service",
                "timestamp": time.time(),
                "external_request": external_request_data
            })
            
        except Exception as e:
            error_counter.add(1, {"type": "external_request_error"})
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"External request endpoint failed: {str(e)}")
            
            return jsonify({
                "status": "error",
                "service": "fabrik-service",
                "error": str(e)
            }), 500

@app.route('/api/redis/stats')
def redis_stats():
    """Get Redis statistics"""
    with tracer.start_as_current_span("redis_stats", kind=trace.SpanKind.SERVER) as span:
        try:
            info = redis_client.info()
            keys_count = redis_client.dbsize()
            
            redis_operations_counter.add(1, {"operation": "stats"})
            
            span.set_attribute("redis.keys_count", keys_count)
            span.set_attribute("redis.memory_used", info.get('used_memory', 0))
            
            return jsonify({
                "status": "success",
                "service": "fabrik-service",
                "redis_stats": {
                    "keys_count": keys_count,
                    "memory_used_bytes": info.get('used_memory', 0),
                    "memory_used_human": info.get('used_memory_human', 'unknown'),
                    "connected_clients": info.get('connected_clients', 0),
                    "uptime_seconds": info.get('uptime_in_seconds', 0)
                }
            })
        except Exception as e:
            error_counter.add(1, {"type": "redis_stats_error"})
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"Failed to get Redis stats: {str(e)}")
            return jsonify({
                "status": "error",
                "service": "fabrik-service",
                "error": str(e)
            }), 500

@app.route('/api/redis/cleanup')
def redis_cleanup():
    """Clean up Redis to avoid disk growth"""
    with tracer.start_as_current_span("redis_cleanup", kind=trace.SpanKind.SERVER) as span:
        try:
            # Get all fabrik keys
            keys = redis_client.keys("fabrik:*")
            deleted_count = 0
            
            if keys:
                deleted_count = redis_client.delete(*keys)
                redis_operations_counter.add(1, {"operation": "cleanup"})
            
            span.set_attribute("redis.keys_deleted", deleted_count)
            
            logger.info(f"Redis cleanup completed. Deleted {deleted_count} keys")
            return jsonify({
                "status": "success",
                "service": "fabrik-service",
                "cleanup_result": {
                    "keys_deleted": deleted_count,
                    "keys_found": len(keys)
                }
            })
        except Exception as e:
            error_counter.add(1, {"type": "redis_cleanup_error"})
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"Redis cleanup failed: {str(e)}")
            return jsonify({
                "status": "error",
                "service": "fabrik-service",
                "error": str(e)
            }), 500

if __name__ == '__main__':
    logger.info("Starting fabrik-service with OpenTelemetry instrumentation")
    logger.info(f"Redis connection: {REDIS_HOST}:{REDIS_PORT}")
    logger.info("OpenTelemetry configured via OTEL_EXPORTER_OTLP_ENDPOINT environment variable")
    logger.info("fabrik-service is ready to receive requests")
    app.run(host='0.0.0.0', port=8080, debug=False)

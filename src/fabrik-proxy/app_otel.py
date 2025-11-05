import os
import requests
import logging
import json
import random
import threading
import time
import pika
from flask import Flask, jsonify, request
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.pika import PikaInstrumentor
from opentelemetry.trace import Status, StatusCode

app = Flask("fabrik-proxy-otel")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FABRIK_SERVICE_URL = os.getenv('FABRIK_SERVICE_URL', 'http://fabrik-service:8080')
# OpenTelemetry will use OTEL_EXPORTER_OTLP_ENDPOINT automatically
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'fabrik')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'fabrik123')

# Global flag for message consumer
consumer_running = False

# Initialize OpenTelemetry
def init_otel():
    print(f"[OTEL INIT] Starting OpenTelemetry initialization for fabrik-proxy")
    print(f"[OTEL INIT] Using OTEL_EXPORTER_OTLP_ENDPOINT environment variable for automatic configuration")

    try:
        # Use OpenTelemetry's automatic configuration
        from opentelemetry import trace, metrics
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource

        # Create resource with service information
        resource = Resource.create({
            "service.name": "fabrik-proxy",
            "service.version": "1.0.0",
            "service.namespace": "fabrik"
        })

        # Configure tracing - OTLP will use OTEL_EXPORTER_OTLP_ENDPOINT automatically
        trace_exporter = OTLPSpanExporter()
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(trace_exporter))
        print(f"[OTEL INIT] Trace exporter configured successfully")

        # Configure metrics - OTLP will use OTEL_EXPORTER_OTLP_ENDPOINT automatically
        metric_exporter = OTLPMetricExporter()
        metric_reader = PeriodicExportingMetricReader(exporter=metric_exporter, export_interval_millis=10000)
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        print(f"[OTEL INIT] Metric exporter configured successfully")

        print(f"[OTEL INIT] OpenTelemetry initialization completed successfully")

    except Exception as e:
        print(f"[OTEL INIT] ERROR: Failed to initialize OpenTelemetry: {str(e)}")
        raise

# Initialize OTEL
init_otel()

# Get tracer and meter
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create custom metrics
request_counter = meter.create_counter(
    "fabrik_proxy_requests_total",
    description="Total number of requests processed by proxy"
)

# Instrument Flask, requests, and Pika
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
PikaInstrumentor().instrument()

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
    """Process received message with OpenTelemetry semantic attributes"""
    with tracer.start_as_current_span("message_process", kind=trace.SpanKind.CONSUMER) as span:
        try:
            # Set messaging semantic attributes
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination.name", method.routing_key)
            span.set_attribute("messaging.destination.kind", "queue")
            span.set_attribute("messaging.operation.type", "process")
            span.set_attribute("messaging.source.kind", "queue")
            span.set_attribute("server.address", RABBITMQ_HOST)
            span.set_attribute("server.port", 5672)

            # Random chance of message processing failure (5%)
            if random.random() < 0.05:
                logger.error("Simulated message processing failure")
                span.set_status(Status(StatusCode.ERROR, "Simulated message processing failure"))
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

            message_data = json.loads(body)
            span.set_attribute("messaging.message.id", message_data.get('id', 'unknown'))
            span.set_attribute("messaging.message.payload_size_bytes", len(body))

            logger.info(f"Processing message: {message_data.get('id', 'unknown')} from queue {method.routing_key}")

            # Simulate processing time
            import time
            processing_time = random.uniform(0.1, 0.5)
            time.sleep(processing_time)
            span.set_attribute("messaging.processing_time_ms", processing_time * 1000)

            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            span.set_status(Status(StatusCode.OK))
            logger.info(f"Message processed successfully: {message_data.get('id', 'unknown')}")

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            span.set_status(Status(StatusCode.ERROR, str(e)))
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
        "instrumentation": "opentelemetry",
        "message_consumer_running": consumer_running
    })

@app.route('/api/proxy', methods=['GET', 'POST'])
def proxy_request():
    """Proxy requests to fabrik-service"""
    logger.info(f"Received request at /api/proxy endpoint")
    request_counter.add(1, {"endpoint": "/api/proxy"})

    with tracer.start_as_current_span("proxy_request") as span:
        span.set_attribute("service.name", "fabrik-proxy")
        span.set_attribute("operation", "proxy_request")
        span.set_attribute("upstream.service", "fabrik-service")

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
            span.set_attribute("http.url", upstream_url)
            span.set_attribute("http.method", "POST")
            span.set_attribute("client.id", headers.get('X-Client-ID', 'unknown'))
            span.set_attribute("correlation.id", headers.get('X-Correlation-ID', 'unknown'))

            response = requests.post(upstream_url, json=payload, headers=headers, timeout=10)

            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_size", len(response.content))

            logger.info(f"Received response from fabrik-service: {response.status_code}")

            if response.status_code == 200:
                logger.info(f"Successfully proxied request to fabrik-service")
                return jsonify({
                    "status": "success",
                    "proxy": "fabrik-proxy",
                    "instrumentation": "opentelemetry",
                    "upstream_response": response.json()
                })
            else:
                span.set_attribute("error", True)
                span.set_attribute("error.type", "upstream_error")
                logger.error(f"Upstream service returned {response.status_code}: {response.text}")
                return jsonify({
                    "status": "error",
                    "proxy": "fabrik-proxy",
                    "instrumentation": "opentelemetry",
                    "error": f"Upstream service returned {response.status_code}",
                    "upstream_response": response.text
                }), response.status_code

        except requests.exceptions.RequestException as e:
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"Request exception when calling {upstream_url}: {str(e)}")
            return jsonify({
                "status": "error",
                "proxy": "fabrik-proxy",
                "instrumentation": "opentelemetry",
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
    logger.info("Starting fabrik-proxy with OpenTelemetry instrumentation")
    logger.info(f"fabrik-service URL: {FABRIK_SERVICE_URL}")
    logger.info("OpenTelemetry configured via OTEL_EXPORTER_OTLP_ENDPOINT environment variable")

    # Check fabrik-service health
    check_fabrik_service_health()

    # Start message consumer in background
    logger.info("Starting message consumer in background thread")
    consumer_thread = threading.Thread(target=start_message_consumer, daemon=True)
    consumer_thread.start()

    logger.info("fabrik-proxy is ready to receive requests and process messages")
    app.run(host='0.0.0.0', port=8080, debug=False)

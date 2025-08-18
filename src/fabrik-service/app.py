import os
import time
import random
import json
import logging
import requests
import redis
from flask import Flask, jsonify
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

app = Flask(__name__)

# Configuration
DYNATRACE_ENDPOINT = os.getenv('DYNATRACE_ENDPOINT', 'http://localhost:4318')
DYNATRACE_API_TOKEN = os.getenv('DYNATRACE_API_TOKEN', '')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

# Initialize OpenTelemetry
def init_otel():
    print(f"[OTEL INIT] Starting OpenTelemetry initialization for fabrik-service")
    print(f"[OTEL INIT] Dynatrace endpoint: {DYNATRACE_ENDPOINT}")
    print(f"[OTEL INIT] API token configured: {'Yes' if DYNATRACE_API_TOKEN else 'No'}")
    
    # Headers for Dynatrace
    headers = {}
    if DYNATRACE_API_TOKEN:
        headers = {"Authorization": f"Api-Token {DYNATRACE_API_TOKEN}"}
        print(f"[OTEL INIT] Using API token authentication")
    else:
        print(f"[OTEL INIT] WARNING: No API token configured")
    
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
        print(f"[OTEL INIT] Setting up trace exporter to {DYNATRACE_ENDPOINT}/v1/traces")
        trace_exporter = OTLPSpanExporter(
            endpoint=f"{DYNATRACE_ENDPOINT}/v1/traces",
            headers=headers
        )
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(
            BatchSpanProcessor(trace_exporter)
        )
        print(f"[OTEL INIT] Trace exporter configured successfully")
        
        # Metrics
        print(f"[OTEL INIT] Setting up metric exporter to {DYNATRACE_ENDPOINT}/v1/metrics")
        metric_exporter = OTLPMetricExporter(
            endpoint=f"{DYNATRACE_ENDPOINT}/v1/metrics",
            headers=headers
        )
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=10000
        )
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        print(f"[OTEL INIT] Metric exporter configured successfully")
        
        # Logs
        print(f"[OTEL INIT] Setting up log exporter to {DYNATRACE_ENDPOINT}/v1/logs")
        log_exporter = OTLPLogExporter(
            endpoint=f"{DYNATRACE_ENDPOINT}/v1/logs",
            headers=headers
        )
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

# Instrument Flask and Redis
FlaskInstrumentor().instrument_app(app)
RedisInstrumentor().instrument()

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Logger
logger = logging.getLogger(__name__)
logger.addHandler(console_handler)
logger.setLevel(logging.INFO)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "fabrik-service"})

@app.route('/api/process')
def process_request():
    """Main processing endpoint - returns 200, some 500s, writes to Redis"""
    logger.info("Received request at /api/process endpoint")
    request_counter.add(1, {"endpoint": "/api/process"})
    
    with tracer.start_as_current_span("process_request") as span:
        span.set_attribute("service.name", "fabrik-service")
        span.set_attribute("operation", "process_request")
        
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
        
        # Make external HTTP request occasionally (40% chance)
        external_request_data = None
        if random.random() < 0.4:
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
            
        if external_request_data:
            response_data["external_request"] = external_request_data
        
        logger.info(f"Successfully processed request {response_data['request_id']}")
        return jsonify(response_data)

def make_external_request():
    """Make external HTTP requests to httpstatus testing endpoints"""
    with tracer.start_as_current_span("external_request") as span:
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
    with tracer.start_as_current_span("redis_write") as span:
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
    
    with tracer.start_as_current_span("external_request_endpoint") as span:
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
    with tracer.start_as_current_span("redis_stats") as span:
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
    with tracer.start_as_current_span("redis_cleanup") as span:
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
    logger.info(f"Dynatrace endpoint: {DYNATRACE_ENDPOINT}")
    logger.info("fabrik-service is ready to receive requests")
    app.run(host='0.0.0.0', port=8080, debug=False)

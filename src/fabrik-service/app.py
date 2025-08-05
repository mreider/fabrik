import os
import time
import random
import json
import logging
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
    # Headers for Dynatrace
    headers = {}
    if DYNATRACE_API_TOKEN:
        headers = {"Authorization": f"Api-Token {DYNATRACE_API_TOKEN}"}
    
    # Traces
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{DYNATRACE_ENDPOINT}/v1/traces",
        headers=headers
    )
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(trace_exporter)
    )
    
    # Metrics
    metric_exporter = OTLPMetricExporter(
        endpoint=f"{DYNATRACE_ENDPOINT}/v1/metrics",
        headers=headers
    )
    metric_reader = PeriodicExportingMetricReader(
        exporter=metric_exporter,
        export_interval_millis=10000
    )
    metrics.set_meter_provider(MeterProvider(metric_readers=[metric_reader]))
    
    # Logs
    log_exporter = OTLPLogExporter(
        endpoint=f"{DYNATRACE_ENDPOINT}/v1/logs",
        headers=headers
    )
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )
    
    # Configure logging
    handler = LoggingHandler(logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

# Initialize OTEL
init_otel()

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

# Instrument Flask and Redis
FlaskInstrumentor().instrument_app(app)
RedisInstrumentor().instrument()

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Logger
logger = logging.getLogger(__name__)

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "fabrik-service"})

@app.route('/api/process')
def process_request():
    """Main processing endpoint - returns 200, some 500s, writes to Redis"""
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
        
        logger.info(f"Successfully processed request {response_data['request_id']}")
        return jsonify(response_data)

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
    app.run(host='0.0.0.0', port=8080, debug=False)

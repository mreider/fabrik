import os
import time
import random
import requests
import logging
import threading
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
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__)

# Configuration
DYNATRACE_ENDPOINT = os.getenv('DYNATRACE_ENDPOINT', 'http://localhost:4318')
DYNATRACE_API_TOKEN = os.getenv('DYNATRACE_API_TOKEN', '')

# Initialize OpenTelemetry
def init_otel():
    # Headers for Dynatrace
    headers = {}
    if DYNATRACE_API_TOKEN:
        headers = {"Authorization": f"Api-Token {DYNATRACE_API_TOKEN}"}
    
    # Import resource for proper service identification
    from opentelemetry.sdk.resources import Resource
    
    # Create resource with service information
    resource = Resource.create({
        "service.name": "fabrik-proxy",
        "service.version": "1.0.0",
        "service.namespace": "fabrik"
    })
    
    # Traces
    trace_exporter = OTLPSpanExporter(
        endpoint=f"{DYNATRACE_ENDPOINT}/v1/traces",
        headers=headers
    )
    trace.set_tracer_provider(TracerProvider(resource=resource))
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
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
    
    # Logs
    log_exporter = OTLPLogExporter(
        endpoint=f"{DYNATRACE_ENDPOINT}/v1/logs",
        headers=headers
    )
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )
    
    # Configure logging
    handler = LoggingHandler(logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)

# Always initialize OpenTelemetry
print(f"[OTEL INIT] Initializing OpenTelemetry for fabrik-proxy")
print(f"[OTEL INIT] Dynatrace endpoint: {DYNATRACE_ENDPOINT}")
print(f"[OTEL INIT] API token configured: {'Yes' if DYNATRACE_API_TOKEN else 'No'}")

try:
    init_otel()
    print(f"[OTEL INIT] OpenTelemetry initialization completed successfully")
except Exception as e:
    print(f"[OTEL INIT] ERROR: Failed to initialize OpenTelemetry: {str(e)}")
    # Fallback to basic tracing if initialization fails
    trace.set_tracer_provider(TracerProvider())
    print(f"[OTEL INIT] Fallback: Basic tracing provider set")

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create custom metrics
proxy_requests_counter = meter.create_counter(
    "fabrik_proxy_requests_total",
    description="Total number of proxy requests"
)

proxy_errors_counter = meter.create_counter(
    "fabrik_proxy_errors_total",
    description="Total number of proxy errors"
)

# Instrument Flask and requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

# Logger
logger = logging.getLogger(__name__)

# Configuration
FABRIK_SERVICE_URL = os.getenv('FABRIK_SERVICE_URL', 'http://fabrik-service:8080')
LOAD_GENERATOR_ENABLED = os.getenv('LOAD_GENERATOR_ENABLED', 'true').lower() == 'true'
LOAD_INTERVAL_MIN = int(os.getenv('LOAD_INTERVAL_MIN', '3'))  # minimum seconds between requests
LOAD_INTERVAL_MAX = int(os.getenv('LOAD_INTERVAL_MAX', '8'))  # maximum seconds between requests

# Global flag to control load generator
load_generator_running = False

def background_load_generator():
    """Background thread that generates continuous load"""
    global load_generator_running
    load_generator_running = True
    
    logger.info("Background load generator started - calling proxy endpoint")
    
    # Wait a bit for the app to fully start
    time.sleep(10)
    
    while load_generator_running:
        try:
            # Random interval between requests
            interval = random.uniform(LOAD_INTERVAL_MIN, LOAD_INTERVAL_MAX)
            time.sleep(interval)
            
            if not load_generator_running:
                break
                
            # Make a request to our own proxy endpoint
            with tracer.start_as_current_span("background_load_request") as span:
                span.set_attribute("service.name", "fabrik-proxy")
                span.set_attribute("operation", "background_load_generator")
                span.set_attribute("load.interval", interval)
                
                try:
                    # Call our own proxy endpoint (which will then call fabrik-service)
                    response = requests.get("http://localhost:8080/api/proxy", timeout=10)
                    span.set_attribute("http.status_code", response.status_code)
                    
                    if response.status_code == 200:
                        logger.info(f"Background load request successful (interval: {interval:.1f}s)")
                    else:
                        logger.warning(f"Background load request returned {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    logger.error(f"Background load request failed: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in background load generator: {str(e)}")
            time.sleep(5)  # Wait before retrying
    
    logger.info("Background load generator stopped")

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "fabrik-proxy",
        "load_generator_enabled": LOAD_GENERATOR_ENABLED,
        "load_generator_running": load_generator_running
    })

@app.route('/api/load/start')
def start_load_generator():
    """Start the background load generator"""
    global load_generator_running
    if not load_generator_running and LOAD_GENERATOR_ENABLED:
        thread = threading.Thread(target=background_load_generator, daemon=True)
        thread.start()
        return jsonify({"status": "started", "message": "Background load generator started"})
    elif load_generator_running:
        return jsonify({"status": "already_running", "message": "Background load generator is already running"})
    else:
        return jsonify({"status": "disabled", "message": "Load generator is disabled"})

@app.route('/api/load/stop')
def stop_load_generator():
    """Stop the background load generator"""
    global load_generator_running
    if load_generator_running:
        load_generator_running = False
        return jsonify({"status": "stopped", "message": "Background load generator stopped"})
    else:
        return jsonify({"status": "not_running", "message": "Background load generator is not running"})

@app.route('/api/load/status')
def load_generator_status():
    """Get the status of the background load generator"""
    return jsonify({
        "enabled": LOAD_GENERATOR_ENABLED,
        "running": load_generator_running,
        "interval_range": f"{LOAD_INTERVAL_MIN}-{LOAD_INTERVAL_MAX} seconds"
    })

@app.route('/api/proxy')
def proxy_request():
    """Proxy requests to fabrik-service"""
    proxy_requests_counter.add(1, {"endpoint": "/api/proxy"})
    
    logger.info(f"Attempting to proxy request to {FABRIK_SERVICE_URL}/api/process")
    
    try:
        with tracer.start_as_current_span("proxy_request") as span:
            span.set_attribute("service.name", "fabrik-proxy")
            span.set_attribute("operation", "proxy_to_fabrik_service")
            span.set_attribute("upstream.url", f"{FABRIK_SERVICE_URL}/api/process")
            
            # Call fabrik-service
            logger.info(f"Making request to: {FABRIK_SERVICE_URL}/api/process")
            response = requests.get(f"{FABRIK_SERVICE_URL}/api/process", timeout=10)
            
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("response.size", len(response.content))
            
            logger.info(f"Received response from fabrik-service: {response.status_code}")
            
            if response.status_code == 200:
                logger.info(f"Successfully proxied request to fabrik-service")
                return jsonify({
                    "status": "success",
                    "proxy": "fabrik-proxy",
                    "upstream_response": response.json()
                })
            else:
                proxy_errors_counter.add(1, {"type": "upstream_error"})
                span.set_attribute("error", True)
                logger.error(f"Upstream service returned {response.status_code}: {response.text}")
                return jsonify({
                    "status": "error",
                    "proxy": "fabrik-proxy",
                    "error": f"Upstream service returned {response.status_code}",
                    "upstream_response": response.text
                }), response.status_code
                
    except requests.exceptions.RequestException as e:
        proxy_errors_counter.add(1, {"type": "request_exception"})
        with tracer.start_as_current_span("proxy_error") as error_span:
            error_span.set_attribute("error", True)
            error_span.set_attribute("error.message", str(e))
            
        logger.error(f"Request exception when calling {FABRIK_SERVICE_URL}/api/process: {str(e)}")
        return jsonify({
            "status": "error",
            "proxy": "fabrik-proxy",
            "error": str(e),
            "upstream_url": f"{FABRIK_SERVICE_URL}/api/process"
        }), 500

@app.route('/api/load')
def generate_load():
    """Generate some load by making multiple requests"""
    results = []
    num_requests = random.randint(3, 8)
    
    with tracer.start_as_current_span("generate_load") as span:
        span.set_attribute("load.requests_count", num_requests)
        
        for i in range(num_requests):
            try:
                response = requests.get(f"{FABRIK_SERVICE_URL}/api/process", timeout=5)
                results.append({
                    "request": i + 1,
                    "status": response.status_code,
                    "success": response.status_code == 200
                })
                # Small delay between requests
                time.sleep(random.uniform(0.1, 0.3))
            except Exception as e:
                results.append({
                    "request": i + 1,
                    "status": "error",
                    "error": str(e),
                    "success": False
                })
    
    return jsonify({
        "status": "completed",
        "proxy": "fabrik-proxy",
        "load_test_results": results,
        "total_requests": num_requests,
        "successful_requests": sum(1 for r in results if r.get("success", False))
    })

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
    logger.info(f"Starting fabrik-proxy with load generator {'enabled' if LOAD_GENERATOR_ENABLED else 'disabled'}")
    logger.info(f"fabrik-service URL: {FABRIK_SERVICE_URL}")
    
    # Check fabrik-service health
    check_fabrik_service_health()
    
    # Start the background load generator automatically if enabled
    if LOAD_GENERATOR_ENABLED:
        logger.info("Starting background load generator automatically")
        thread = threading.Thread(target=background_load_generator, daemon=True)
        thread.start()
    
    app.run(host='0.0.0.0', port=8080, debug=False)

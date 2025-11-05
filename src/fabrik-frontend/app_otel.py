import os
import time
import random
import requests
import logging
import threading
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
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode

app = Flask("fabrik-frontend-otel")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
FABRIK_SERVICE_URL = os.getenv('FABRIK_SERVICE_URL', 'http://fabrik-service.fabrik:8080')
FABRIK_PROXY_URL = os.getenv('FABRIK_PROXY_URL', 'http://nginx.fabrik-otel:80')
LOAD_GENERATOR_ENABLED = os.getenv('LOAD_GENERATOR_ENABLED', 'true').lower() == 'true'
LOAD_INTERVAL_MIN = int(os.getenv('LOAD_INTERVAL_MIN', '3'))  # minimum seconds between requests
LOAD_INTERVAL_MAX = int(os.getenv('LOAD_INTERVAL_MAX', '8'))  # maximum seconds between requests

# Global flag to control load generator
load_generator_running = False

# Initialize OpenTelemetry
def init_otel():
    print(f"[OTEL INIT] Starting OpenTelemetry initialization for fabrik-frontend")

    try:
        # Get configuration from environment
        dt_endpoint = os.getenv('DYNATRACE_ENDPOINT', os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'))
        dt_token = os.getenv('DYNATRACE_API_TOKEN', '')

        if not dt_endpoint or not dt_token:
            print(f"[OTEL INIT] ERROR: Missing DYNATRACE_ENDPOINT or DYNATRACE_API_TOKEN")
            return

        # Construct proper OTLP endpoint for traces
        if not dt_endpoint.endswith('/api/v2/otlp/v1/traces'):
            if dt_endpoint.endswith('/api/v2/otlp'):
                trace_endpoint = dt_endpoint + '/v1/traces'
                metric_endpoint = dt_endpoint + '/v1/metrics'
            else:
                trace_endpoint = dt_endpoint + '/api/v2/otlp/v1/traces'
                metric_endpoint = dt_endpoint + '/api/v2/otlp/v1/metrics'
        else:
            trace_endpoint = dt_endpoint
            metric_endpoint = dt_endpoint.replace('/traces', '/metrics')

        headers = {"Authorization": f"Api-Token {dt_token}"}
        print(f"[OTEL INIT] Using trace endpoint: {trace_endpoint}")

        # Create resource with service information
        resource = Resource.create({
            "service.name": "fabrik-frontend-otel",
            "service.version": "1.0.0",
            "service.namespace": "fabrik"
        })

        # Configure tracing with explicit headers
        trace_exporter = OTLPSpanExporter(endpoint=trace_endpoint, headers=headers)
        trace.set_tracer_provider(TracerProvider(resource=resource))
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(trace_exporter))
        print(f"[OTEL INIT] Trace exporter configured successfully")

        # Configure metrics with explicit headers
        metric_exporter = OTLPMetricExporter(endpoint=metric_endpoint, headers=headers)
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

# Instrument Flask and requests
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

def background_load_generator():
    """Background thread that generates continuous load to fabrik-proxy"""
    global load_generator_running
    load_generator_running = True
    
    logger.info("Background load generator started - calling fabrik-proxy endpoint")
    
    # Wait a bit for the app to fully start
    time.sleep(10)
    
    while load_generator_running:
        try:
            # Random interval between requests
            interval = random.uniform(LOAD_INTERVAL_MIN, LOAD_INTERVAL_MAX)
            time.sleep(interval)
            
            if not load_generator_running:
                break
                
            try:
                # Call fabrik-proxy endpoint with POST and headers
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Fabrik-Frontend/1.0 (Load Generator)',
                    'X-Client-ID': f'frontend-{random.randint(1000, 9999)}',
                    'X-Request-Source': 'background-load-generator',
                    'X-Correlation-ID': f'load-{int(time.time())}-{random.randint(100, 999)}'
                }
                payload = {
                    'client_info': {
                        'user_agent': 'Fabrik-Frontend/1.0 (Load Generator)',
                        'client_id': headers['X-Client-ID'],
                        'request_source': 'background-load-generator'
                    },
                    'request_data': {
                        'operation': 'proxy_request',
                        'timestamp': time.time(),
                        'load_generator': True
                    }
                }
                response = requests.post(f"{FABRIK_PROXY_URL}/api/proxy",
                                       json=payload, headers=headers, timeout=10)

                if response.status_code == 200:
                    logger.info(f"Background load request to proxy successful (interval: {interval:.1f}s)")
                else:
                    logger.warning(f"Background load request to proxy returned {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Background load request to proxy failed: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in background load generator: {str(e)}")
            time.sleep(5)  # Wait before retrying
    
    logger.info("Background load generator stopped")

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "fabrik-frontend",
        "instrumentation": "otel",
        "load_generator_enabled": LOAD_GENERATOR_ENABLED,
        "load_generator_running": load_generator_running,
        "service_url": FABRIK_SERVICE_URL
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
        "interval_range": f"{LOAD_INTERVAL_MIN}-{LOAD_INTERVAL_MAX} seconds",
        "target_url": f"{FABRIK_PROXY_URL}/api/proxy"
    })

@app.route('/api/call-proxy', methods=['GET', 'POST'])
def call_proxy():
    """Make a single call to the fabrik-proxy"""
    logger.info(f"Making single request to fabrik-proxy: {FABRIK_PROXY_URL}/api/proxy")

    try:
        # Prepare headers with client information
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': request.headers.get('User-Agent', 'Fabrik-Frontend/1.0'),
            'X-Client-ID': f'frontend-api-{random.randint(1000, 9999)}',
            'X-Request-Source': 'api-endpoint',
            'X-Correlation-ID': f'api-{int(time.time())}-{random.randint(100, 999)}'
        }
        payload = {
            'client_info': {
                'user_agent': headers['User-Agent'],
                'client_id': headers['X-Client-ID'],
                'request_source': 'api-endpoint',
                'forwarded_headers': dict(request.headers)
            },
            'request_data': {
                'operation': 'api_call_proxy',
                'timestamp': time.time(),
                'load_generator': False
            }
        }
        response = requests.post(f"{FABRIK_PROXY_URL}/api/proxy",
                               json=payload, headers=headers, timeout=10)

        logger.info(f"Received response from fabrik-service: {response.status_code}")

        if response.status_code == 200:
            logger.info(f"Successfully called fabrik-service")
            return jsonify({
                "status": "success",
                "frontend": "fabrik-frontend",
                "instrumentation": "otel",
                "service_response": response.json()
            })
        else:
            logger.error(f"Service returned {response.status_code}: {response.text}")
            return jsonify({
                "status": "error",
                "frontend": "fabrik-frontend",
                "instrumentation": "otel",
                "error": f"Service returned {response.status_code}",
                "service_response": response.text
            }), response.status_code

    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception when calling service: {str(e)}")
        return jsonify({
            "status": "error",
            "frontend": "fabrik-frontend",
            "instrumentation": "otel",
            "error": str(e),
            "service_url": f"{FABRIK_SERVICE_URL}/api/process"
        }), 500

@app.route('/api/load')
def generate_load():
    """Generate load by making multiple requests to fabrik-proxy"""
    results = []
    num_requests = random.randint(3, 8)
    
    logger.info(f"Generating load with {num_requests} requests to fabrik-proxy")
    
    for i in range(num_requests):
        try:
            # Prepare headers and payload for POST request
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Fabrik-Frontend/1.0 (Load Test)',
                'X-Client-ID': f'frontend-load-{random.randint(1000, 9999)}',
                'X-Request-Source': 'load-test',
                'X-Correlation-ID': f'load-test-{int(time.time())}-{random.randint(100, 999)}'
            }
            payload = {
                'client_info': {
                    'user_agent': headers['User-Agent'],
                    'client_id': headers['X-Client-ID'],
                    'request_source': 'load-test'
                },
                'request_data': {
                    'operation': 'load_test',
                    'timestamp': time.time(),
                    'request_number': i + 1
                }
            }
            response = requests.post(f"{FABRIK_PROXY_URL}/api/proxy",
                                   json=payload, headers=headers, timeout=5)
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
    
    successful_requests = sum(1 for r in results if r.get("success", False))
    logger.info(f"Load generation completed: {successful_requests}/{num_requests} successful requests to proxy")
    
    return jsonify({
        "status": "completed",
        "frontend": "fabrik-frontend",
        "instrumentation": "otel",
        "load_test_results": results,
        "total_requests": num_requests,
        "successful_requests": successful_requests,
        "target_url": f"{FABRIK_PROXY_URL}/api/proxy"
    })

def check_fabrik_proxy_health():
    """Check if fabrik-proxy is reachable"""
    try:
        logger.info(f"Checking fabrik-proxy health at {FABRIK_PROXY_URL}/health")
        response = requests.get(f"{FABRIK_PROXY_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("fabrik-proxy is healthy and reachable")
            return True
        else:
            logger.warning(f"fabrik-proxy health check returned {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"fabrik-proxy health check failed: {str(e)}")
        return False

if __name__ == '__main__':
    logger.info("Starting fabrik-frontend with OneAgent instrumentation")
    logger.info(f"fabrik-proxy URL: {FABRIK_PROXY_URL}")
    logger.info(f"Load generator {'enabled' if LOAD_GENERATOR_ENABLED else 'disabled'}")
    
    # Check fabrik-proxy health
    check_fabrik_proxy_health()
    
    # Start the background load generator automatically if enabled
    if LOAD_GENERATOR_ENABLED:
        logger.info("Starting background load generator automatically")
        thread = threading.Thread(target=background_load_generator, daemon=True)
        thread.start()
    
    logger.info("fabrik-frontend is ready to send requests to fabrik-proxy")
    app.run(host='0.0.0.0', port=8080, debug=False)

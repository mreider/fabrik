import os
import time
import random
import requests
import logging
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

# Initialize OTEL only if we have Dynatrace configuration
if DYNATRACE_ENDPOINT and DYNATRACE_API_TOKEN:
    init_otel()
else:
    # For OneAgent deployment, just set up basic tracing
    trace.set_tracer_provider(TracerProvider())

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

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "service": "fabrik-proxy"})

@app.route('/api/proxy')
def proxy_request():
    """Proxy requests to fabrik-service"""
    proxy_requests_counter.add(1, {"endpoint": "/api/proxy"})
    
    try:
        with tracer.start_as_current_span("proxy_request") as span:
            span.set_attribute("service.name", "fabrik-proxy")
            span.set_attribute("operation", "proxy_to_fabrik_service")
            
            # Call fabrik-service
            response = requests.get(f"{FABRIK_SERVICE_URL}/api/process", timeout=10)
            
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("response.size", len(response.content))
            
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
                logger.error(f"Upstream service returned {response.status_code}")
                return jsonify({
                    "status": "error",
                    "proxy": "fabrik-proxy",
                    "error": f"Upstream service returned {response.status_code}"
                }), response.status_code
                
    except requests.exceptions.RequestException as e:
        proxy_errors_counter.add(1, {"type": "request_exception"})
        with tracer.start_as_current_span("proxy_error") as error_span:
            error_span.set_attribute("error", True)
            error_span.set_attribute("error.message", str(e))
            
        logger.error(f"Request exception: {str(e)}")
        return jsonify({
            "status": "error",
            "proxy": "fabrik-proxy",
            "error": str(e)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)

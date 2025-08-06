import os
import time
import random
import requests
import logging
import threading
from flask import Flask, jsonify

app = Flask(__name__)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
                
            try:
                # Call our own proxy endpoint (which will then call fabrik-service)
                response = requests.get("http://localhost:8080/api/proxy", timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"Background load request successful (interval: {interval:.1f}s)")
                else:
                    logger.warning(f"Background load request returned {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
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
        "instrumentation": "oneagent",
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
    logger.info(f"Attempting to proxy request to {FABRIK_SERVICE_URL}/api/process")
    
    try:
        # Call fabrik-service
        logger.info(f"Making request to: {FABRIK_SERVICE_URL}/api/process")
        response = requests.get(f"{FABRIK_SERVICE_URL}/api/process", timeout=10)
        
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
        logger.error(f"Request exception when calling {FABRIK_SERVICE_URL}/api/process: {str(e)}")
        return jsonify({
            "status": "error",
            "proxy": "fabrik-proxy",
            "instrumentation": "oneagent",
            "error": str(e),
            "upstream_url": f"{FABRIK_SERVICE_URL}/api/process"
        }), 500

@app.route('/api/load')
def generate_load():
    """Generate some load by making multiple requests"""
    results = []
    num_requests = random.randint(3, 8)
    
    logger.info(f"Generating load with {num_requests} requests")
    
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
    
    successful_requests = sum(1 for r in results if r.get("success", False))
    logger.info(f"Load generation completed: {successful_requests}/{num_requests} successful requests")
    
    return jsonify({
        "status": "completed",
        "proxy": "fabrik-proxy",
        "instrumentation": "oneagent",
        "load_test_results": results,
        "total_requests": num_requests,
        "successful_requests": successful_requests
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
    logger.info("Starting fabrik-proxy with OneAgent instrumentation")
    logger.info(f"fabrik-service URL: {FABRIK_SERVICE_URL}")
    logger.info(f"Load generator {'enabled' if LOAD_GENERATOR_ENABLED else 'disabled'}")
    
    # Check fabrik-service health
    check_fabrik_service_health()
    
    # Start the background load generator automatically if enabled
    if LOAD_GENERATOR_ENABLED:
        logger.info("Starting background load generator automatically")
        thread = threading.Thread(target=background_load_generator, daemon=True)
        thread.start()
    
    logger.info("fabrik-proxy is ready to receive requests")
    app.run(host='0.0.0.0', port=8080, debug=False)

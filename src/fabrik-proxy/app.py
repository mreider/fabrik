import os
import requests
import logging
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

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "service": "fabrik-proxy",
        "instrumentation": "oneagent"
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
    
    logger.info("fabrik-proxy is ready to receive requests")
    app.run(host='0.0.0.0', port=8080, debug=False)

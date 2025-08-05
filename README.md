# Fabrik Demo Application

A simple microservices demo application for testing Dynatrace observability with both OneAgent and OpenTelemetry instrumentation.

## Architecture

The Fabrik application consists of:

- **fabrik-proxy**: A Python Flask service that acts as a proxy, instrumented with OneAgent in the `fabrik-oneagent` namespace and with OpenTelemetry in the `fabrik-otel` namespace
- **fabrik-service**: A Python Flask service that processes requests, writes to Redis, and returns responses (including some random 500 errors). Always instrumented with OpenTelemetry
- **Redis**: A Redis instance for data storage

## Features

- **fabrik-proxy** forwards requests to fabrik-service
- **fabrik-service** returns 200 responses most of the time, but randomly returns 500 errors (20% chance)
- **fabrik-service** occasionally writes data to Redis (30% chance) with automatic expiration
- **fabrik-service** provides Redis cleanup endpoint to prevent disk growth
- Both services include comprehensive OpenTelemetry instrumentation (traces, metrics, logs)
- Dual deployment modes: OneAgent and OpenTelemetry

## Deployment Options

The application deploys to two namespaces with different instrumentation approaches:

### OneAgent Deployment (`fabrik-oneagent` namespace)
- fabrik-proxy: Instrumented with OneAgent (automatic instrumentation)
- fabrik-service: Instrumented with OpenTelemetry (manual instrumentation)
- Deployment files: `k8s/oneagent-fabrik-proxy.yaml`, `k8s/oneagent-fabrik-service.yaml`

### OpenTelemetry Deployment (`fabrik-otel` namespace)
- fabrik-proxy: Instrumented with OpenTelemetry (manual instrumentation)
- fabrik-service: Instrumented with OpenTelemetry (manual instrumentation)
- Deployment files: `k8s/otel-fabrik-proxy.yaml`, `k8s/otel-fabrik-service.yaml`

## Prerequisites

1. Kubernetes cluster
2. kubectl configured
3. Dynatrace environment with API tokens

## Setup

1. **Configure Dynatrace secrets**:
   ```bash
   # Copy and fill in the Dynatrace operator secret template
   cp k8s/dynakube-operator-secret.yaml.template k8s/dynakube-operator-secret.yaml
   # Edit k8s/dynakube-operator-secret.yaml with your tokens
   
   # Update k8s/dynatrace-secret.yaml with your Dynatrace endpoint and API token
   ```

2. **Deploy the application**:
   ```bash
   ./deploy.sh
   ```

## Testing

### Test fabrik-otel namespace:
```bash
kubectl port-forward -n fabrik-otel svc/fabrik-proxy 8080:8080

# Test proxy endpoint
curl http://localhost:8080/api/proxy

# Test load generation
curl http://localhost:8080/api/load

# Test health
curl http://localhost:8080/health
```

### Test fabrik-oneagent namespace:
```bash
kubectl port-forward -n fabrik-oneagent svc/fabrik-proxy 8081:8080

# Test proxy endpoint
curl http://localhost:8081/api/proxy

# Test load generation
curl http://localhost:8081/api/load

# Test health
curl http://localhost:8081/health
```

### Test fabrik-service directly:
```bash
kubectl port-forward -n fabrik-otel svc/fabrik-service 8082:8080

# Test processing endpoint
curl http://localhost:8082/api/process

# Test Redis stats
curl http://localhost:8082/api/redis/stats

# Test Redis cleanup
curl http://localhost:8082/api/redis/cleanup
```

## API Endpoints

### fabrik-proxy
- `GET /health` - Health check
- `GET /api/proxy` - Proxy request to fabrik-service
- `GET /api/load` - Generate load by making multiple requests to fabrik-service

### fabrik-service
- `GET /health` - Health check
- `GET /api/process` - Main processing endpoint (returns 200 or random 500s, writes to Redis)
- `GET /api/redis/stats` - Get Redis statistics
- `GET /api/redis/cleanup` - Clean up Redis keys to prevent disk growth

## Monitoring

The application generates:
- **Traces**: Request flows between services
- **Metrics**: Custom metrics for requests, errors, and Redis operations
- **Logs**: Structured logs with correlation IDs
- **Errors**: Simulated 500 errors for testing error tracking

## Container Images

Images are built and pushed to GitHub Container Registry:
- `ghcr.io/mreider/fabrik-proxy:latest`
- `ghcr.io/mreider/fabrik-service:latest`

## Development

To build images locally:
```bash
# Build fabrik-proxy
docker build -t fabrik-proxy ./src/fabrik-proxy

# Build fabrik-service  
docker build -t fabrik-service ./src/fabrik-service
```

## Cleanup

To remove the deployment:
```bash
kubectl delete namespace fabrik-otel fabrik-oneagent

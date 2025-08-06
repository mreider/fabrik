# Fabrik Demo Application

A simple microservices demo application for testing Dynatrace observability with both OneAgent and OpenTelemetry instrumentation.

## Architecture

The Fabrik application consists of:

- **fabrik-proxy**: A Python Flask service that acts as a proxy, instrumented with OneAgent (automatic instrumentation)
- **fabrik-service**: A Python Flask service that processes requests, writes to Redis, and returns responses (including some random 500 errors). Instrumented with OpenTelemetry (manual instrumentation)
- **Redis**: A Redis instance for data storage

## Features

- **fabrik-proxy** forwards requests to fabrik-service (OneAgent -> OTEL instrumentation flow)
- **Automatic load generation**: fabrik-proxy generates continuous background load every 3-8 seconds
- **fabrik-service** returns 200 responses most of the time, but randomly returns 500 errors (20% chance)
- **fabrik-service** occasionally writes data to Redis (30% chance) with automatic expiration
- **fabrik-service** provides Redis cleanup endpoint to prevent disk growth
- Mixed instrumentation approach allows comparison of OneAgent vs OpenTelemetry within the same application flow
- Comprehensive observability with traces, metrics, and logs
- Load generator can be controlled via API endpoints

## Deployment Options

The application deploys to a single `fabrik` namespace with mixed instrumentation approaches:

### Mixed Instrumentation (`fabrik` namespace)
- **fabrik-proxy**: Instrumented with OneAgent (automatic instrumentation)
- **fabrik-service**: Instrumented with OpenTelemetry (manual instrumentation)
- **Redis**: Standard Redis deployment

This setup allows you to compare OneAgent vs OpenTelemetry instrumentation within the same namespace and application flow.

**Deployment files:**
- `k8s/fabrik-proxy.yaml` - OneAgent instrumented proxy service
- `k8s/fabrik-service.yaml` - OpenTelemetry instrumented backend service  
- `k8s/redis.yaml` - Redis data store
- `k8s/namespaces.yaml` - Single fabrik namespace with both inject and enrich labels

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
   
   # Copy and fill in the Dynatrace OTEL secret template
   cp k8s/dynatrace-secret.yaml.template k8s/dynatrace-secret.yaml
   # Edit k8s/dynatrace-secret.yaml with your Dynatrace endpoint and API token
   ```

2. **Deploy the application**:
   ```bash
   ./deploy.sh
   ```

## Testing

### Test the fabrik application:
```bash
kubectl port-forward -n fabrik svc/fabrik-proxy 8080:8080

# Test proxy endpoint (OneAgent -> OTEL flow)
curl http://localhost:8080/api/proxy

# Test load generation
curl http://localhost:8080/api/load

# Test health
curl http://localhost:8080/health
```

### Test fabrik-service directly:
```bash
kubectl port-forward -n fabrik svc/fabrik-service 8081:8080

# Test processing endpoint (OTEL instrumented)
curl http://localhost:8081/api/process

# Test Redis stats
curl http://localhost:8081/api/redis/stats

# Test Redis cleanup
curl http://localhost:8081/api/redis/cleanup
```

## API Endpoints

### fabrik-proxy
- `GET /health` - Health check (includes load generator status)
- `GET /api/proxy` - Proxy request to fabrik-service
- `GET /api/load` - Generate load by making multiple requests to fabrik-service
- `GET /api/load/status` - Get background load generator status
- `GET /api/load/start` - Start background load generator
- `GET /api/load/stop` - Stop background load generator

### fabrik-service
- `GET /health` - Health check
- `GET /api/process` - Main processing endpoint (returns 200 or random 500s, writes to Redis)
- `GET /api/redis/stats` - Get Redis statistics
- `GET /api/redis/cleanup` - Clean up Redis keys to prevent disk growth

## Load Generator

The fabrik-proxy includes an automatic background load generator that:
- Starts automatically when the service starts (configurable via `LOAD_GENERATOR_ENABLED`)
- Makes requests to its own `/api/proxy` endpoint every 3-8 seconds (configurable)
- Creates continuous OneAgent → OTEL instrumentation flow for testing
- Can be controlled via API endpoints

**Environment Variables:**
- `LOAD_GENERATOR_ENABLED` - Enable/disable load generator (default: `true`)
- `LOAD_INTERVAL_MIN` - Minimum seconds between requests (default: `3`)
- `LOAD_INTERVAL_MAX` - Maximum seconds between requests (default: `8`)

**Control the load generator:**
```bash
# Check status
curl http://localhost:8080/api/load/status

# Start load generator
curl http://localhost:8080/api/load/start

# Stop load generator
curl http://localhost:8080/api/load/stop
```

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
./destroy.sh
# or manually:
kubectl delete namespace fabrik

# Architecture Changes - Load Generation Refactor

## Overview
Refactored the load generation architecture to separate concerns and improve observability tracing by removing self-load generation from the proxy service and creating a dedicated frontend service.

## Changes Made

### 1. Created New fabrik-frontend Service
- **Location**: `src/fabrik-frontend/`
- **Purpose**: Dedicated load generator that sends requests to fabrik-proxy
- **Instrumentation**: OneAgent only (no OpenTelemetry libraries)
- **Key Features**:
  - Background load generator with configurable intervals
  - Manual load generation endpoints
  - Health check endpoint
  - Proxy connectivity testing

### 2. Updated fabrik-proxy Service
- **Removed**: All self-load generation functionality
- **Removed**: Background load generator threads
- **Removed**: Load generator control endpoints (`/api/load/start`, `/api/load/stop`, `/api/load/status`)
- **Removed**: Manual load generation endpoint (`/api/load`)
- **Kept**: Core proxy functionality (`/api/proxy`, `/health`)
- **Result**: Clean proxy service focused solely on proxying requests to fabrik-service

### 3. Service Architecture Flow
```
fabrik-frontend → fabrik-proxy → fabrik-service → Redis
```

**Before**: fabrik-proxy → fabrik-proxy (self-load) → fabrik-service
**After**: fabrik-frontend → fabrik-proxy → fabrik-service

### 4. OneAgent Injection Configuration
All services now use the correct OneAgent injection annotation:
- `dynatrace.com/inject: "true"` (matches DynaKube namespace selector)
- Fixed previous incorrect annotation `dynatrace.com/inject-oneagent: "true"`

### 5. Kubernetes Manifests
- **New**: `k8s/fabrik-frontend.yaml` - Frontend service deployment and service
- **Updated**: `k8s/fabrik-proxy.yaml` - Fixed OneAgent injection annotation
- **Updated**: `deploy.sh` - Added frontend deployment and updated testing instructions
- **Unchanged**: `destroy.sh` - Still works by deleting entire fabrik namespace

### 6. Environment Configuration
**fabrik-frontend environment variables**:
- `FABRIK_PROXY_URL`: Target proxy service URL
- `LOAD_GENERATOR_ENABLED`: Enable/disable automatic load generation
- `LOAD_INTERVAL_MIN/MAX`: Configure load generation intervals

**fabrik-proxy environment variables**:
- `FABRIK_SERVICE_URL`: Target service URL (unchanged)
- Removed all load generator related variables

### 7. API Endpoints

**fabrik-frontend**:
- `GET /health` - Health check with load generator status
- `GET /api/call-proxy` - Single request to proxy
- `GET /api/load` - Generate burst load to proxy
- `GET /api/load/start` - Start background load generator
- `GET /api/load/stop` - Stop background load generator
- `GET /api/load/status` - Load generator status

**fabrik-proxy** (simplified):
- `GET /health` - Health check
- `GET /api/proxy` - Proxy request to fabrik-service

### 8. Testing Instructions
Updated testing flow:
1. Port-forward to fabrik-frontend (port 8080) for load generation
2. Port-forward to fabrik-proxy (port 8081) for direct proxy testing
3. Port-forward to fabrik-service (port 8082) for direct service testing

## Benefits
1. **Cleaner Architecture**: Each service has a single responsibility
2. **Better Observability**: Clear request flow for tracing
3. **Improved OneAgent Injection**: Fixed annotation issues
4. **No Self-Referencing**: Eliminated problematic self-load patterns
5. **Easier Debugging**: Isolated load generation from proxy logic

## Deployment
Run `./deploy.sh` to deploy all services including the new frontend.
The frontend will automatically start generating background load to the proxy upon startup.

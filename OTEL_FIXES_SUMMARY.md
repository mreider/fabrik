# OpenTelemetry Fixes for Fabrik App

## Problem
OpenTelemetry traces were not reaching Dynatrace in the fabrik app, while they worked correctly in the gesund app.

## Root Causes Identified

1. **Missing Environment Variables**: Fabrik deployments were missing critical OpenTelemetry environment variables that gesund had
2. **Conditional Initialization**: fabrik-proxy had problematic conditional logic that prevented OpenTelemetry initialization when API token was missing
3. **Missing Resource Attributes**: Python services weren't properly identifying themselves with service names and metadata
4. **Incomplete Configuration**: fabrik-proxy deployment was missing Dynatrace endpoint and API token environment variables entirely

## Changes Made

### 1. Kubernetes Deployment Updates

#### fabrik-service.yaml
Added missing environment variables:
```yaml
# OpenTelemetry configuration
- name: OTEL_SDK_DISABLED
  value: "false"
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: "http/protobuf"
- name: OTEL_SERVICE_NAME
  value: "fabrik-service"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.name=fabrik-service,service.version=1.0.0"
```

#### fabrik-proxy.yaml
Added missing Dynatrace and OpenTelemetry environment variables:
```yaml
- name: DYNATRACE_ENDPOINT
  valueFrom:
    secretKeyRef:
      name: dynatrace-secret
      key: endpoint
- name: DYNATRACE_API_TOKEN
  valueFrom:
    secretKeyRef:
      name: dynatrace-secret
      key: api-token
# OpenTelemetry configuration
- name: OTEL_SDK_DISABLED
  value: "false"
- name: OTEL_EXPORTER_OTLP_PROTOCOL
  value: "http/protobuf"
- name: OTEL_SERVICE_NAME
  value: "fabrik-proxy"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.name=fabrik-proxy,service.version=1.0.0"
```

### 2. Python Code Updates

#### fabrik-service/app.py
- Added proper Resource configuration with service identification
- Enhanced logging for better debugging
- Improved error handling in OpenTelemetry initialization

#### fabrik-proxy/app.py
- **CRITICAL FIX**: Removed conditional initialization that prevented OpenTelemetry setup
- Added proper Resource configuration
- Added fallback mechanism with better error handling
- Enhanced logging for debugging

#### Requirements Updates
- Added `requests==2.31.0` to fabrik-service requirements.txt

### 3. Key Differences from Gesund App

**Gesund (Java - Working)**:
- Uses OpenTelemetry Java agent with auto-instrumentation
- Environment variables automatically configure the agent
- Spring Boot application with minimal manual configuration

**Fabrik (Python - Fixed)**:
- Uses manual OpenTelemetry SDK configuration
- Required explicit Resource configuration for service identification
- Needed proper initialization logic without conditional blocks

## Verification Steps

After deploying these changes:

1. Check pod logs for OpenTelemetry initialization messages:
   ```bash
   kubectl logs -n fabrik deployment/fabrik-service
   kubectl logs -n fabrik deployment/fabrik-proxy
   ```

2. Look for these log messages:
   - `[OTEL INIT] Starting OpenTelemetry initialization`
   - `[OTEL INIT] OpenTelemetry initialization completed successfully`

3. Verify traces appear in Dynatrace within a few minutes of generating traffic

4. Test endpoints:
   - `http://fabrik-proxy/api/proxy` - should generate traces across both services
   - `http://fabrik-service/api/process` - should generate service-specific traces

## Environment Variables Now Consistent

Both fabrik services now have the same OpenTelemetry environment variables as the working gesund services:
- `OTEL_SDK_DISABLED=false`
- `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
- `OTEL_SERVICE_NAME` (service-specific)
- `OTEL_RESOURCE_ATTRIBUTES` (service-specific)
- `DYNATRACE_ENDPOINT` (from secret)
- `DYNATRACE_API_TOKEN` (from secret)

## Next Steps

1. Redeploy the fabrik application with these changes
2. Monitor logs for successful OpenTelemetry initialization
3. Generate some traffic to test trace collection
4. Verify traces appear in Dynatrace dashboard

The main issue was the missing environment variables and the conditional initialization logic in the Python code that prevented proper OpenTelemetry setup.

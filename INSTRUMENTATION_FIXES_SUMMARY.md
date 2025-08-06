# Fabrik Instrumentation Configuration Fixes

## Summary of Changes

This document summarizes the fixes applied to properly configure the fabrik application with the correct instrumentation:

### Requirements
- **fabrik-proxy**: Should use OneAgent instrumentation
- **fabrik-service**: Should use OpenTelemetry (OTEL) instrumentation
- **Namespace**: Properly labeled for Dynatrace injection based on DynaKube configuration

## Changes Made

### 1. Namespace Configuration (`k8s/namespaces.yaml`)
- **Status**: ✅ Already correctly configured
- **Labels**:
  - `dynatrace.com/inject: "true"` - Enables OneAgent injection for the namespace
  - `dynatrace.com/enrich: "true"` - Enables metadata enrichment
  - `instrumentation: mixed` - Indicates mixed instrumentation approach

### 2. DynaKube Configuration (`k8s/dynakube.yaml`)
- **Status**: ✅ Already correctly configured
- **OneAgent injection**: Configured to inject into namespaces with `dynatrace.com/inject: "true"`
- **Metadata enrichment**: Configured for namespaces with `dynatrace.com/enrich: "true"`

### 3. Fabrik-Proxy Configuration (`k8s/fabrik-proxy.yaml`)
- **Status**: ✅ Completely cleaned up
- **Changes**:
  - ✅ Kept `dynatrace.com/inject-oneagent: "true"` annotation
  - ✅ **REMOVED** all Dynatrace endpoint and API token configurations (OneAgent handles this)
  - ✅ **REMOVED** all OTEL environment variables (not needed with OneAgent)
  - ✅ Simplified to only essential configuration

### 3a. Fabrik-Proxy Application Code (`src/fabrik-proxy/app.py`)
- **Status**: ✅ Completely rewritten
- **Changes**:
  - ✅ **REMOVED** all OpenTelemetry imports and dependencies
  - ✅ **REMOVED** all OTEL initialization code
  - ✅ **SIMPLIFIED** to use only standard Python logging
  - ✅ **ADDED** instrumentation indicators in response payloads
  - ✅ Clean, simple code that relies on OneAgent for all instrumentation

### 3b. Fabrik-Proxy Dependencies (`src/fabrik-proxy/requirements.txt`)
- **Status**: ✅ Cleaned up
- **Changes**:
  - ✅ **REMOVED** all OpenTelemetry packages:
    - `opentelemetry-api`
    - `opentelemetry-sdk`
    - `opentelemetry-instrumentation-flask`
    - `opentelemetry-instrumentation-requests`
    - `opentelemetry-exporter-otlp-proto-http`
  - ✅ **KEPT** only essential packages: Flask and requests

### 4. Fabrik-Service Configuration (`k8s/fabrik-service.yaml`)
- **Status**: ✅ Fixed
- **Changes**:
  - ✅ **ADDED** `dynatrace.com/inject-oneagent: "false"` annotation to prevent OneAgent injection
  - ✅ **KEPT** all OpenTelemetry environment variables:
    - `OTEL_SDK_DISABLED: "false"`
    - `OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf"`
    - `OTEL_SERVICE_NAME: "fabrik-service"`
    - `OTEL_RESOURCE_ATTRIBUTES: "service.name=fabrik-service,service.version=1.0.0"`
  - ✅ **ADDED** `OTEL_EXPORTER_OTLP_ENDPOINT: "http://dynatrace-activegate.dynatrace:14499/otlp"`
  - ✅ Kept Dynatrace API credentials for direct API calls

### 5. Redis Configuration (`k8s/redis.yaml`)
- **Status**: ✅ No changes needed
- **Note**: Redis will inherit OneAgent injection from namespace labels, which is appropriate for infrastructure monitoring

## Final Configuration Summary

| Component | Instrumentation | Injection Annotation | OTEL Config | Notes |
|-----------|----------------|---------------------|-------------|-------|
| fabrik-proxy | OneAgent | `inject-oneagent: "true"` | ❌ Removed | Uses OneAgent for APM |
| fabrik-service | OpenTelemetry | `inject-oneagent: "false"` | ✅ Present | Uses OTEL SDK with Dynatrace endpoint |
| redis | OneAgent (inherited) | None (inherits from namespace) | N/A | Infrastructure monitoring via OneAgent |

## Verification Steps

To verify the configuration is working correctly:

1. **Deploy the application**:
   ```bash
   ./deploy.sh
   ```

2. **Check pod annotations**:
   ```bash
   kubectl get pods -n fabrik -o yaml | grep -A5 -B5 "dynatrace.com"
   ```

3. **Verify OneAgent injection on fabrik-proxy**:
   ```bash
   kubectl describe pod -n fabrik -l app=fabrik-proxy | grep -i dynatrace
   ```

4. **Verify OTEL configuration on fabrik-service**:
   ```bash
   kubectl exec -n fabrik deployment/fabrik-service -- env | grep OTEL
   ```

5. **Check logs for instrumentation**:
   ```bash
   kubectl logs -n fabrik -l app=fabrik-proxy
   kubectl logs -n fabrik -l app=fabrik-service
   ```

## Expected Behavior

- **fabrik-proxy**: Should show OneAgent injection in pod annotations and Dynatrace agent processes
- **fabrik-service**: Should show OTEL SDK initialization in logs and send telemetry to Dynatrace ActiveGate
- **Both services**: Should appear in Dynatrace with proper service detection and monitoring

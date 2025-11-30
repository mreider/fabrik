#!/bin/bash
#
# Setup script for Dynatrace Auto-Remediation
# Validates prerequisites and helps configure the auto-remediation loop
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "======================================"
echo "🚀 FABRIK AUTO-REMEDIATION SETUP"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

check_env_var() {
    if [[ -n "${!1}" ]]; then
        echo -e "${GREEN}✓${NC} $1 is set"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not set"
        return 1
    fi
}

check_k8s_resource() {
    local resource_type=$1
    local resource_name=$2
    local namespace=$3
    
    if kubectl get "$resource_type" "$resource_name" -n "$namespace" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $resource_type/$resource_name exists in $namespace"
        return 0
    else
        echo -e "${RED}✗${NC} $resource_type/$resource_name not found in $namespace"
        return 1
    fi
}

echo "Step 1: Checking Prerequisites"
echo "======================================"

ALL_CHECKS_PASSED=true

# Check required commands
check_command "kubectl" || ALL_CHECKS_PASSED=false
check_command "curl" || ALL_CHECKS_PASSED=false
check_command "jq" || echo -e "${YELLOW}⚠${NC}  jq not installed (optional, recommended for JSON parsing)"

# Check environment variables
echo ""
echo "Step 2: Checking Environment Variables"
echo "======================================"

check_env_var "DT_API_URL" || {
    echo -e "${YELLOW}→${NC} Set with: export DT_API_URL='https://your-environment.live.dynatrace.com'"
    ALL_CHECKS_PASSED=false
}

check_env_var "DT_API_TOKEN" || {
    echo -e "${YELLOW}→${NC} Set with: export DT_API_TOKEN='dt0c01.YOUR_TOKEN_HERE'"
    echo -e "${YELLOW}→${NC} Required scopes: events.ingest, slo.read, slo.write, automation.workflows.read, automation.workflows.write"
    ALL_CHECKS_PASSED=false
}

# Check Kubernetes access
echo ""
echo "Step 3: Checking Kubernetes Access"
echo "======================================"

if kubectl cluster-info &>/dev/null; then
    echo -e "${GREEN}✓${NC} kubectl can connect to cluster"
    
    # Check namespaces
    check_k8s_resource "namespace" "fabrik-oa" "" || echo -e "${YELLOW}→${NC} Create with: kubectl apply -f k8s/namespaces.yaml"
    check_k8s_resource "namespace" "fabrik-ot" "" || echo -e "${YELLOW}→${NC} Create with: kubectl apply -f k8s/namespaces.yaml"
    check_k8s_resource "namespace" "fabrik-oa-2" "" || echo -e "${YELLOW}→${NC} Create with: kubectl apply -f k8s/namespaces.yaml"
    
    # Check deployments
    echo ""
    check_k8s_resource "deployment" "fulfillment" "fabrik-oa" || {
        echo -e "${YELLOW}→${NC} Deploy with: kubectl apply -f k8s/fabrik-oa.yaml"
        ALL_CHECKS_PASSED=false
    }
else
    echo -e "${RED}✗${NC} kubectl cannot connect to cluster"
    ALL_CHECKS_PASSED=false
fi

# Check if chaos is currently active
echo ""
echo "Step 4: Checking Current Chaos State"
echo "======================================"

for ns in fabrik-oa fabrik-ot fabrik-oa-2; do
    if kubectl get namespace "$ns" &>/dev/null; then
        for service in fulfillment orders inventory shipping-receiver shipping-processor frontend; do
            if kubectl get deployment "$service" -n "$ns" &>/dev/null 2>&1; then
                failure_rate=$(kubectl get deployment "$service" -n "$ns" -o jsonpath="{.spec.template.spec.containers[0].env[?(@.name=='FAILURE_RATE')].value}" 2>/dev/null || echo "")
                if [[ -n "$failure_rate" ]]; then
                    echo -e "${YELLOW}⚠${NC}  Chaos active on $ns/$service: FAILURE_RATE=$failure_rate"
                else
                    echo -e "${GREEN}✓${NC} $ns/$service: No chaos active"
                fi
            fi
        done
    fi
done

# Summary
echo ""
echo "======================================"
if [[ "$ALL_CHECKS_PASSED" == "true" ]]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Create SLO in Dynatrace:"
    echo "     ${SCRIPT_DIR}/../dynatrace/README.md (Step 1)"
    echo ""
    echo "  2. Create Site Reliability Guardian:"
    echo "     ${SCRIPT_DIR}/../dynatrace/README.md (Step 2)"
    echo ""
    echo "  3. Set up Kubernetes service account:"
    echo "     ${SCRIPT_DIR}/../dynatrace/README.md (Step 3)"
    echo ""
    echo "  4. Create Workflow:"
    echo "     ${SCRIPT_DIR}/../dynatrace/README.md (Step 4)"
    echo ""
    echo "  5. Test the loop:"
    echo "     kubectl exec -n default -it deploy/argo -- /app/simulate.sh manual"
else
    echo -e "${RED}❌ Some checks failed${NC}"
    echo ""
    echo "Please fix the issues above before proceeding with setup."
fi
echo "======================================"
echo ""

# Offer to create service account
if [[ "$ALL_CHECKS_PASSED" == "true" ]]; then
    read -p "Would you like to create the Kubernetes service account now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Creating Kubernetes service account..."
        
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: dynatrace-automation
  namespace: fabrik-oa
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dynatrace-chaos-remediation
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: dynatrace-chaos-remediation
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: dynatrace-chaos-remediation
subjects:
- kind: ServiceAccount
  name: dynatrace-automation
  namespace: fabrik-oa
EOF
        
        echo ""
        echo -e "${GREEN}✅ Service account created${NC}"
        echo ""
        echo "Generate token with:"
        echo "  kubectl create token dynatrace-automation -n fabrik-oa --duration=87600h"
        echo ""
        echo "Use this token in Dynatrace Kubernetes integration setup."
    fi
fi

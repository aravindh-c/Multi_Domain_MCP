#!/bin/bash
# Export current Kubernetes resources (multi-tenant-chatbot namespace) to YAML
# Use this to backup live state before teardown; repo manifests remain source of truth for recreate.
# Output: infrastructure/export/k8s-export-<timestamp>.yaml

set -e

NAMESPACE="multi-tenant-chatbot"
EXPORT_DIR="infrastructure/export"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
OUTFILE="${EXPORT_DIR}/k8s-export-${TIMESTAMP}.yaml"

mkdir -p "${EXPORT_DIR}"

echo "Exporting K8s resources from namespace ${NAMESPACE} to ${OUTFILE}..."

kubectl get all,ingress,configmap,secret,pvc,serviceaccount,networkpolicy -n "${NAMESPACE}" -o yaml > "${OUTFILE}"

echo "Export written to ${OUTFILE}"
echo "To restore from this file is not automated; use repo manifests and deploy.sh for recreate."

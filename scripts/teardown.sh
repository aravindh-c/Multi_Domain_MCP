#!/bin/bash
# Teardown multitenant-chatbot: remove app and optionally the EKS cluster
# Account: 026544696832 | Region: us-east-1
# Usage:
#   ./teardown.sh              # Delete app only (namespace); cluster stays
#   ./teardown.sh --full       # Delete app then delete EKS cluster

set -e

NAMESPACE="multi-tenant-chatbot"
EKSCTL_CONFIG="infrastructure/eksctl-config.yaml"
FULL=""

for arg in "$@"; do
  case $arg in
    --full) FULL=1 ;;
  esac
done

echo "Teardown multitenant-chatbot (namespace: ${NAMESPACE})..."

# 1. Delete Kubernetes app (namespace removes all resources: deployments, services, ingress, ALB, etc.)
echo "Deleting namespace ${NAMESPACE} (this removes all app resources and the internal ALB)..."
kubectl delete namespace "${NAMESPACE}" --ignore-not-found=true --timeout=120s 2>/dev/null || true

echo "App teardown complete. Namespace ${NAMESPACE} removed."

if [ -n "${FULL}" ]; then
  if [ ! -f "${EKSCTL_CONFIG}" ]; then
    echo "EKS config not found: ${EKSCTL_CONFIG}. Skipping cluster delete."
    exit 0
  fi
  echo "Deleting EKS cluster (eksctl delete cluster -f ${EKSCTL_CONFIG})..."
  eksctl delete cluster -f "${EKSCTL_CONFIG}"
  echo "Full teardown complete. Cluster deleted. ECR repos and Secrets Manager secret are left; delete manually if desired."
else
  echo "Cluster left running. To delete cluster later: ./teardown.sh --full"
  echo "To recreate app only: ./deploy.sh"
fi

#!/bin/bash
# Deployment script for multitenant-chatbot
# Account: 026544696831 | Region: us-east-1 | Internal only | Max 3 users

set -e

NAMESPACE="multi-tenant-chatbot"
REGION="${AWS_REGION:-us-east-1}"

echo "Deploying multitenant-chatbot to EKS (region: ${REGION})..."

# Create namespace
echo "Creating namespace..."
kubectl apply -f infrastructure/kubernetes/namespace.yaml

# Create service accounts with IRSA
echo "Creating service accounts..."
kubectl apply -f infrastructure/kubernetes/irsa-service-accounts.yaml

# Create K8s secrets (for orchestrator/rag; also use Secrets Manager via IRSA)
if [ -n "${OPENAI_API_KEY}" ]; then
  echo "Creating K8s secrets..."
  kubectl create secret generic orchestrator-secrets \
    --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
    --from-literal=LANGSMITH_API_KEY="${LANGSMITH_API_KEY:-}" \
    -n ${NAMESPACE} \
    --dry-run=client -o yaml | kubectl apply -f -

  kubectl create secret generic rag-secrets \
    --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY}" \
    -n ${NAMESPACE} \
    --dry-run=client -o yaml | kubectl apply -f -
else
  echo "OPENAI_API_KEY not set; skip K8s secrets (ensure Secrets Manager secret multitenant-chatbot-secrets exists and IRSA can read it)."
fi

# Deploy services (order: vLLM -> RAG -> orchestrator -> router)
echo "Deploying vLLM (GPU nodes)..."
kubectl apply -f infrastructure/kubernetes/vllm-deployment.yaml

echo "Deploying RAG service..."
kubectl apply -f infrastructure/kubernetes/rag-deployment.yaml

echo "Deploying orchestrator..."
kubectl apply -f infrastructure/kubernetes/orchestrator-deployment.yaml

echo "Deploying request router..."
kubectl apply -f infrastructure/kubernetes/router-deployment.yaml

# Apply network policies
echo "Applying network policies..."
kubectl apply -f infrastructure/kubernetes/network-policies.yaml

# Deploy internal ingress
echo "Deploying internal ingress..."
kubectl apply -f infrastructure/kubernetes/ingress.yaml

echo "Deployment complete!"
echo "Check status: kubectl get pods -n ${NAMESPACE}"
echo "Internal ALB hostname: kubectl get ingress -n ${NAMESPACE}"

# Kubernetes Deployment Guide

## Prerequisites

1. EKS cluster with:
   - CPU node group (for API/Router/Orchestrator/RAG)
   - GPU node group (for vLLM/TGI)
   - ALB Ingress Controller installed
   - IRSA (IAM Roles for Service Accounts) configured

2. AWS Resources:
   - ECR repository for container images
   - Secrets Manager secret with API keys
   - IAM roles for service accounts
   - ACM certificate for HTTPS

## Deployment Steps

### 1. Create Namespace
```bash
kubectl apply -f namespace.yaml
```

### 2. Create Service Accounts with IRSA
```bash
# Update IRSA role ARNs in irsa-service-accounts.yaml
kubectl apply -f irsa-service-accounts.yaml
```

### 3. Create Secrets
```bash
# Create secret for orchestrator (API keys)
kubectl create secret generic orchestrator-secrets \
  --from-literal=OPENAI_API_KEY=<key> \
  --from-literal=LANGSMITH_API_KEY=<key> \
  -n multi-tenant-chatbot

# Create secret for RAG service
kubectl create secret generic rag-secrets \
  --from-literal=OPENAI_API_KEY=<key> \
  -n multi-tenant-chatbot
```

### 4. Deploy Services
```bash
# Deploy in order
kubectl apply -f vllm-deployment.yaml  # GPU nodes
kubectl apply -f rag-deployment.yaml
kubectl apply -f orchestrator-deployment.yaml
kubectl apply -f router-deployment.yaml
```

### 5. Deploy Ingress
```bash
# Update ACM certificate ARN in ingress.yaml
kubectl apply -f ingress.yaml
```

### 6. Apply Network Policies
```bash
kubectl apply -f network-policies.yaml
```

## Node Labels

Ensure your nodes are labeled correctly:

```bash
# CPU nodes
kubectl label nodes <node-name> node-type=cpu

# GPU nodes
kubectl label nodes <node-name> node-type=gpu accelerator=nvidia-tesla-v100
```

## Verification

```bash
# Check all pods are running
kubectl get pods -n multi-tenant-chatbot

# Check services
kubectl get svc -n multi-tenant-chatbot

# Check ingress
kubectl get ingress -n multi-tenant-chatbot

# View logs
kubectl logs -f deployment/request-router -n multi-tenant-chatbot
```

## Scaling

```bash
# Scale router
kubectl scale deployment request-router --replicas=5 -n multi-tenant-chatbot

# Scale orchestrator
kubectl scale deployment orchestrator --replicas=5 -n multi-tenant-chatbot

# Scale vLLM (GPU nodes)
kubectl scale deployment vllm-inference --replicas=3 -n multi-tenant-chatbot
```

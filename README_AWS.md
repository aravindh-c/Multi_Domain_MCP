# Multi-Tenant AWS Production Architecture

## Overview

This is a production-ready multi-tenant LLM chatbot deployed on AWS EKS with the following architecture:

- **Model ≠ Inference Engine**: LLM models run inference via vLLM/TGI (continuous batching, KV-cache, token streaming)
- **Multi-Tenant Isolation**: Tenant-scoped RAG, RBAC, rate limiting
- **Kubernetes Deployment**: EKS with CPU/GPU node pools
- **Observability**: CloudWatch logs/metrics, optional LangSmith tracing
- **Security**: IRSA, Secrets Manager, network policies

## Architecture Components

### 1. Request Router (`src/router/main.py`)
- Tenant isolation via `X-Tenant-Id` header or JWT
- RBAC/guardrails (blocked tools, sensitive prompts, refusal rules)
- Per-tenant rate limiting
- Routes to Orchestrator service

### 2. Orchestrator (`src/app/main.py`)
- LangGraph workflow for intent routing
- Calls RAG service (tenant-scoped)
- Calls inference engine (vLLM/TGI)
- Generates answers with citations

### 3. Inference Engine (`infrastructure/kubernetes/vllm-deployment.yaml`)
- vLLM/TGI on GPU nodes
- Continuous batching
- KV-cache per request
- Token streaming

### 4. RAG Service (`src/rag/tenant_retriever.py`)
- Tenant namespaced vector DB (FAISS with tenant_id metadata)
- Retrieval with tenant isolation enforced

### 5. Observability (`src/observability/cloudwatch.py`)
- CloudWatch logs (structured JSON)
- CloudWatch metrics (latency, tokens, cost, refusals)
- Optional LangSmith tracing

## Quick Start

### 1. Build Docker Images

```bash
# Build router
docker build -f dockerfiles/Dockerfile.router -t <ECR_REPO>/request-router:latest .

# Build orchestrator
docker build -f dockerfiles/Dockerfile.orchestrator -t <ECR_REPO>/orchestrator:latest .

# Build RAG service
docker build -f dockerfiles/Dockerfile.rag -t <ECR_REPO>/rag-service:latest .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ECR_REPO>
docker push <ECR_REPO>/request-router:latest
docker push <ECR_REPO>/orchestrator:latest
docker push <ECR_REPO>/rag-service:latest
```

### 2. Deploy to EKS

See `infrastructure/kubernetes/README.md` for detailed deployment steps.

### 3. Configure Secrets

Store API keys in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name multi-tenant-chatbot-secrets \
  --secret-string '{"OPENAI_API_KEY":"sk-...","LANGSMITH_API_KEY":"ls-..."}'
```

### 4. Test

```bash
curl -X POST https://chatbot.example.com/chat \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: t1" \
  -d '{
    "tenant_id": "t1",
    "user_id": "u123",
    "session_id": "s456",
    "query": "What is the weather?",
    "locale": "en-US"
  }'
```

## Configuration

### Environment Variables

- `AWS_REGION`: AWS region (default: us-east-1)
- `AWS_ROLE_ARN`: IRSA role ARN
- `SECRETS_MANAGER_SECRET_NAME`: Secrets Manager secret name
- `ORCHESTRATOR_URL`: Orchestrator service URL
- `VLLM_SERVICE_URL`: vLLM service URL
- `RAG_SERVICE_URL`: RAG service URL

### Tenant Configuration

Configure per-tenant settings via `/tenant/{tenant_id}/config` endpoint:

```json
{
  "tenant_id": "t1",
  "blocked_tools": ["mcp_finance"],
  "sensitive_prompt_patterns": ["password", "credit card"],
  "refusal_rules": [{"type": "contains", "pattern": "hack", "reason": "Security violation"}],
  "rate_limit_per_minute": 60,
  "rate_limit_per_hour": 1000,
  "allowed_routes": ["PRICE_COMPARE", "DIET_NUTRITION"]
}
```

## Observability

### CloudWatch Metrics

- `RequestLatency`: Request latency by tenant/route
- `RequestCount`: Request count by tenant/route
- `TokenUsage`: Token usage by tenant/route
- `CostEstimate`: Cost estimate by tenant/route
- `RefusalCount`: Refusal count by tenant/route/reason

### CloudWatch Logs

Structured JSON logs in log group `multi-tenant-chatbot`:
- `tenant_id`: Tenant identifier
- `route`: Intent route
- `latency_ms`: Request latency
- `chunk_ids`: Retrieved chunk IDs
- `citations`: Citations
- `refusal_reason`: Refusal reason (if any)
- `token_usage`: Token usage
- `cost_usd_estimate`: Cost estimate

## Security

- **IRSA**: IAM roles for service accounts (no long-lived credentials)
- **Secrets Manager**: API keys stored securely
- **Network Policies**: Pod-to-pod communication restrictions
- **Tenant Isolation**: Enforced at router, RAG, and application layers

## Scaling

- **Horizontal**: Scale router/orchestrator replicas on CPU nodes
- **Vertical**: Scale vLLM replicas on GPU nodes (limited by GPU availability)
- **Auto-scaling**: Configure HPA based on CPU/memory or custom metrics

## Monitoring

- CloudWatch Dashboards for tenant metrics
- CloudWatch Alarms for error rates, latency
- Optional: LangSmith for detailed tracing

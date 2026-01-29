# Multi-Tenant AWS Production Architecture - Deployment Summary

## ✅ Completed Components

### 1. **Multi-Tenant Schemas** (`src/app/multi_tenant_schemas.py`)
- `MultiTenantChatRequest` with `tenant_id` field
- `TenantConfig` for RBAC and guardrails
- `TenantRateLimit` for rate limiting
- `MultiTenantVaultChunk` with tenant isolation
- `TenantMetrics` for observability

### 2. **Request Router Service** (`src/router/main.py`)
- Tenant isolation via `X-Tenant-Id` header or JWT
- RBAC checks (blocked tools, allowed routes)
- Guardrails (sensitive prompts, refusal rules)
- Per-tenant rate limiting (per minute/hour)
- Routes to Orchestrator service
- CloudWatch metrics emission

### 3. **Inference Engine Client** (`src/inference/vllm_client.py`)
- `VLLMClient` for vLLM integration
- `TGIClient` for TGI integration
- Support for streaming and non-streaming
- OpenAI-compatible API interface
- Error handling and retries

### 4. **CloudWatch Observability** (`src/observability/cloudwatch.py`)
- Structured metrics (latency, tokens, cost, refusals)
- Structured logs with tenant context
- Log group/stream management
- Fallback to standard logging if CloudWatch unavailable

### 5. **Kubernetes Manifests** (`infrastructure/kubernetes/`)
- Namespace configuration
- Router deployment (CPU nodes)
- Orchestrator deployment (CPU nodes)
- vLLM deployment (GPU nodes)
- RAG service deployment (CPU nodes)
- Ingress with ALB
- IRSA service accounts
- Network policies for pod isolation

### 6. **Dockerfiles** (`dockerfiles/`)
- `Dockerfile.router` - Request router service
- `Dockerfile.orchestrator` - Orchestrator service
- `Dockerfile.rag` - RAG service

### 7. **Tenant-Aware RAG** (`src/rag/tenant_retriever.py`)
- `retrieve_for_tenant()` with tenant_id filtering
- Metadata filter enforcement (tenant_id + user_id)
- Defense-in-depth tenant isolation checks
- Compatible with existing MMR/reranking

### 8. **Tenant-Aware Vault Store** (`src/rag/tenant_vault_store.py`)
- `build_index()` with tenant_id in metadata
- Per-tenant/user file structure
- Metadata includes tenant_id for isolation

### 9. **AWS Settings** (`src/app/aws_settings.py`)
- Secrets Manager integration
- IRSA role ARN configuration
- CloudWatch configuration
- Service discovery URLs
- Automatic secret loading

## 📋 Architecture Overview

```
Client → ALB → Request Router (tenant isolation, RBAC, rate limit)
                ↓
         Orchestrator (LangGraph)
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
RAG Service          Inference Engine (vLLM/TGI)
(tenant-scoped)     (GPU nodes, continuous batching)
```

## 🔐 Security Features

1. **Tenant Isolation**:
   - Router validates tenant_id
   - RAG enforces tenant_id in metadata filter
   - Defense-in-depth checks in retrieval

2. **RBAC**:
   - Per-tenant blocked tools
   - Allowed routes per tenant
   - Sensitive prompt patterns

3. **Rate Limiting**:
   - Per-tenant per-minute limits
   - Per-tenant per-hour limits
   - In-memory tracking (use Redis in production)

4. **Network Security**:
   - Network policies restrict pod-to-pod communication
   - IRSA for service accounts (no long-lived credentials)
   - Secrets Manager for API keys

## 📊 Observability

### CloudWatch Metrics
- `RequestLatency` (by tenant/route)
- `RequestCount` (by tenant/route)
- `TokenUsage` (by tenant/route)
- `CostEstimate` (by tenant/route)
- `RefusalCount` (by tenant/route/reason)

### CloudWatch Logs
Structured JSON with:
- tenant_id, route, latency_ms
- chunk_ids, citations
- refusal_reason
- token_usage, cost_usd_estimate

## 🚀 Deployment Steps

1. **Build and push Docker images**:
   ```bash
   docker build -f dockerfiles/Dockerfile.router -t <ECR_REPO>/request-router:latest .
   docker push <ECR_REPO>/request-router:latest
   # Repeat for orchestrator and rag-service
   ```

2. **Configure AWS resources**:
   - Create EKS cluster with CPU/GPU node groups
   - Create IRSA roles
   - Create Secrets Manager secret
   - Create ACM certificate

3. **Deploy to Kubernetes**:
   ```bash
   ./scripts/deploy.sh
   ```

4. **Verify deployment**:
   ```bash
   kubectl get pods -n multi-tenant-chatbot
   kubectl get ingress -n multi-tenant-chatbot
   ```

## 🖥️ How to use the chatbot (UI and API)

The app exposes a **chat UI** and a **REST API**. The ingress is an **internal** ALB, so you can reach it only from inside the VPC (or via port-forward from your machine).

### Option A: Chat UI in the browser

1. **Get the internal ALB hostname** (from a machine that can reach the VPC, or after port-forward):
   ```bash
   kubectl get ingress -n multi-tenant-chatbot
   ```
   Use the **HOST** (or ADDRESS) value, e.g. `k8s-multiten-xxxxx.us-east-1.elb.amazonaws.com`.

2. **If you are outside the VPC**, create a port-forward to the router, then open the UI in your browser:
   ```bash
   kubectl port-forward -n multi-tenant-chatbot svc/request-router-service 8000:8000
   ```
   Then open: **http://127.0.0.1:8000/**  
   You get the chat window; type a message or use the example buttons (Price Compare, Finance, Diet).

3. **If you are inside the VPC** (e.g. bastion or EC2 in the same VPC), open in a browser:
   **http://\<ALB_HOSTNAME\>/**  
   Same chat UI; messages are sent to `POST /chat` on the same host.

### Option B: Call the API with curl

- **With port-forward** (from your laptop):
  ```bash
  kubectl port-forward -n multi-tenant-chatbot svc/request-router-service 8000:8000
  ```
  Then in another terminal:
  ```bash
  curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"tenant_id\":\"t1\",\"user_id\":\"u123\",\"session_id\":\"s1\",\"query\":\"Is paneer okay for dinner?\",\"locale\":\"en-IN\"}"
  ```

- **From inside the VPC** (replace with your ALB hostname):
  ```bash
  curl -X POST http://<ALB_HOSTNAME>/chat -H "Content-Type: application/json" -d "{\"tenant_id\":\"t1\",\"user_id\":\"u123\",\"session_id\":\"s1\",\"query\":\"Is paneer okay for dinner?\",\"locale\":\"en-IN\"}"
  ```

### Summary

| What        | Where |
|------------|--------|
| Chat UI    | **GET /** on the router (browser: same host as API) |
| Chat API   | **POST /chat** with JSON body (`tenant_id`, `user_id`, `session_id`, `query`, `locale`) |
| Health     | **GET /health** |

If you only have the cluster from your laptop, use **port-forward** and open **http://127.0.0.1:8000/** to use the chat window.

## 🔐 One secret, multiple keys (Secrets Manager)

You can store **multiple key-value pairs in a single secret** (e.g. `multitenant-chatbot-secrets1`):

1. **AWS Console:** Secrets Manager → your secret → **Retrieve secret value** → **Edit**.
2. Under **Key/value** add pairs, for example:
   - `OPENAI_API_KEY` = `sk-your-openai-key`
   - `LANGSMITH_API_KEY` = `ls-your-langsmith-key`
3. Save. The orchestrator (and RAG service) load both from this one secret when `SECRETS_MANAGER_SECRET_NAME` is set and the keys are not in the pod env.

The app reads **OPENAI_API_KEY** and **LANGSMITH_API_KEY** from that secret at startup (orchestrator and RAG); no need for separate secrets.

## 📥 Ingesting vault data (diet RAG)

To get real diet answers, the RAG service must have an index. You can **ingest once** after the RAG pod is running:

1. **Port-forward to the RAG service:**
   ```bash
   kubectl port-forward -n multi-tenant-chatbot svc/rag-service 8002:8000
   ```
2. **Call the ingest endpoint** (replace the long string with your vault text, e.g. diet/medical notes):
   ```bash
   curl -X POST http://127.0.0.1:8002/ingest -H "Content-Type: application/json" -d "{\"user_id\":\"u123\",\"text\":\"User is vegetarian. No nuts. Prefers paneer and dal. Allergies: none.\"}"
   ```
3. **Use the same `user_id` in the chat** (e.g. the UI sends `user_id: u123`). Diet queries for that user will then use the ingested chunks.

**Note:** With **emptyDir**, the index is lost when the RAG pod restarts. Re-run the ingest after a restart, or switch to a PVC for persistence.

## 🔄 Next Steps

1. **Production Enhancements**:
   - Replace in-memory rate limiting with Redis
   - Load tenant configs from database
   - Add JWT validation library
   - Implement distributed tracing (X-Ray or Jaeger)

2. **Scaling**:
   - Configure HPA for auto-scaling
   - Set up cluster autoscaler for GPU nodes
   - Implement request queuing for GPU nodes

3. **Monitoring**:
   - Create CloudWatch dashboards
   - Set up CloudWatch alarms
   - Configure SNS notifications

4. **Testing**:
   - Load testing with multiple tenants
   - Tenant isolation testing
   - Rate limiting verification
   - RBAC rule testing

## 📝 Configuration

Update these values before deployment:
- `<ECR_REPO>`: Your ECR repository URL
- `<ACCOUNT_ID>`: Your AWS account ID
- `<ACM_CERT_ARN>`: ACM certificate ARN for HTTPS
- `chatbot.example.com`: Your domain name
- GPU node labels: Adjust based on your GPU type

## 📚 Documentation

- Architecture: `docs/aws_multi_tenant_architecture.md`
- Kubernetes: `infrastructure/kubernetes/README.md`
- AWS Deployment: `README_AWS.md`
- **Export, teardown, and recreate**: [docs/EXPORT_TEARDOWN_RECREATE.md](docs/EXPORT_TEARDOWN_RECREATE.md) – turn off all services and recreate the full setup later from scripts and config.

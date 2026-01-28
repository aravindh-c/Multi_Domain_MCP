# Multi-Tenant AWS Production Architecture

## Overview

Production-style multi-tenant LLM chatbot on AWS using the mental model: **model ≠ inference engine**. The LLM (e.g., LLaMA/Mistral) runs **inference** (forward pass), but efficient multi-user serving is handled by an **inference engine** (vLLM or TGI) that supports **continuous batching**, **KV-cache per request**, GPU scheduling, and **token streaming**.

## Architecture Components

### 1. Request Router Service
- **Location**: CPU nodes (EKS)
- **Responsibilities**:
  - Tenant isolation via `tenant_id` header/JWT claim
  - RBAC/guardrails (blocked tools, sensitive prompts, refusal rules)
  - Per-tenant rate limiting
  - Routes requests to Orchestrator service

### 2. Orchestrator Service (LangGraph)
- **Location**: CPU nodes (EKS)
- **Responsibilities**:
  - Intent routing (SOP/KPI/DataQuery)
  - Retrieves evidence from RAG service (tenant-scoped)
  - Ranks/packs context
  - Calls tools (MCP servers)
  - Generates grounded answers with citations

### 3. Inference Engine (vLLM/TGI)
- **Location**: GPU nodes (EKS)
- **Responsibilities**:
  - Hosts model weights (LLaMA/Mistral)
  - Continuous batching
  - KV-cache per request
  - GPU scheduling
  - Token streaming

### 4. RAG Service
- **Location**: CPU nodes (EKS)
- **Responsibilities**:
  - Tenant namespaced vector DB (metadata filter by tenant_id)
  - FAISS with tenant_id in metadata
  - Retrieval with tenant isolation

### 5. Observability
- **CloudWatch**: Structured logs/metrics (route, latency, chunk_ids, citations, refusal_reason, token/cost placeholders)
- **LangSmith** (optional): Tracing for debugging

### 6. Security
- **IRSA**: IAM roles for service accounts
- **Secrets Manager**: API keys and credentials
- **Network Policies**: Pod-to-pod communication restrictions
- **Per-tenant rate limits**: Enforced at router level

## Deployment

### Kubernetes (EKS)
- **Node Pool Split**:
  - CPU nodes: API Gateway/Router + Orchestrator + RAG/Tools
  - GPU nodes: vLLM/TGI pods hosting model weights
- **Ingress**: ALB Ingress Controller
- **Service Mesh**: Optional (for advanced routing)

## Data Flow

1. Client → ALB → Request Router (tenant isolation, RBAC, rate limit)
2. Request Router → Orchestrator (with tenant_id)
3. Orchestrator → RAG Service (tenant-scoped retrieval)
4. Orchestrator → Inference Engine (vLLM/TGI) for generation
5. Orchestrator → Request Router → Client (with citations, metadata)

## Tenant Isolation

- **Vector DB**: Metadata filter `tenant_id` enforced in code
- **Request Router**: Validates tenant_id from JWT/header
- **RBAC**: Per-tenant tool access rules
- **Rate Limits**: Per-tenant quotas

## Observability Metrics

- Route (SOP/KPI/DataQuery)
- Latency (ms)
- Retrieved chunk_ids
- Citations
- Refusal reason (if any)
- Token usage (prompt/completion/total)
- Cost estimate (USD)

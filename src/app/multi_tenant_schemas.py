"""Multi-tenant schemas with tenant_id support."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MultiTenantChatRequest(BaseModel):
    """Chat request with tenant isolation."""
    tenant_id: str | None = Field(None, description="Tenant identifier (from JWT/header; default t1)")
    user_id: str
    session_id: str
    query: str
    locale: str | None = "en-IN"


class TenantConfig(BaseModel):
    """Per-tenant configuration for RBAC and guardrails."""
    tenant_id: str
    blocked_tools: List[str] = Field(default_factory=list)
    sensitive_prompt_patterns: List[str] = Field(default_factory=list)
    refusal_rules: List[Dict[str, Any]] = Field(default_factory=list)
    rate_limit_per_minute: int = 60
    rate_limit_per_hour: int = 1000
    allowed_routes: List[str] = Field(default_factory=lambda: ["PRICE_COMPARE", "FINANCE_STOCK", "DIET_NUTRITION", "CLARIFY"])


class TenantRateLimit(BaseModel):
    """Rate limit tracking per tenant."""
    tenant_id: str
    requests_per_minute: int = 0
    requests_per_hour: int = 0
    last_reset_minute: float = 0.0
    last_reset_hour: float = 0.0


class MultiTenantVaultChunk(BaseModel):
    """Vault chunk with tenant isolation."""
    tenant_id: str
    user_id: str
    chunk_id: str
    text: str
    source: str = "user_vault"
    confidence_score: float | None = None
    retrieval_method: str = "similarity_search"


class TenantMetrics(BaseModel):
    """Per-tenant observability metrics."""
    tenant_id: str
    route: str
    latency_ms: int
    chunk_ids: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    refusal_reason: Optional[str] = None
    token_usage: Dict[str, int] = Field(default_factory=lambda: {"prompt": 0, "completion": 0, "total": 0})
    cost_usd_estimate: float = 0.0

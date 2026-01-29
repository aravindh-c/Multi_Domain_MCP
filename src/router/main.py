"""Request router service with tenant isolation, RBAC, and rate limiting."""
import logging
import time
from pathlib import Path
from collections import defaultdict
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.app.multi_tenant_schemas import (
    MultiTenantChatRequest,
    TenantConfig,
    TenantMetrics,
    TenantRateLimit,
)
from src.observability.cloudwatch import emit_metrics, log_request

logger = logging.getLogger(__name__)

app = FastAPI(title="Multi-Tenant Request Router")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory tenant configs (in production, load from database/Secrets Manager)
TENANT_CONFIGS: Dict[str, TenantConfig] = {}

# Rate limiting state (in production, use Redis/DynamoDB)
RATE_LIMITS: Dict[str, TenantRateLimit] = defaultdict(
    lambda: TenantRateLimit(tenant_id="", requests_per_minute=0, requests_per_hour=0)
)

# Orchestrator service URL (from env or service discovery)
ORCHESTRATOR_URL = "http://orchestrator-service:8000"

# Chat UI (static files)
static_dir = Path(__file__).resolve().parent.parent.parent / "static"


def get_tenant_id_from_jwt(authorization: Optional[str] = None, x_tenant_id: Optional[str] = Header(None)) -> str:
    """Extract tenant_id from JWT or header."""
    # In production, decode JWT and extract tenant_id claim
    if x_tenant_id:
        return x_tenant_id
    if authorization:
        # TODO: Decode JWT and extract tenant_id
        # For now, assume format: "Bearer <token>" where token contains tenant_id
        pass
    raise HTTPException(status_code=401, detail="Missing tenant_id in header or JWT")


def check_rate_limit(tenant_id: str, config: TenantConfig) -> bool:
    """Check if tenant has exceeded rate limits."""
    now = time.time()
    limit = RATE_LIMITS[tenant_id]
    
    # Reset counters if needed
    if now - limit.last_reset_minute >= 60:
        limit.requests_per_minute = 0
        limit.last_reset_minute = now
    if now - limit.last_reset_hour >= 3600:
        limit.requests_per_hour = 0
        limit.last_reset_hour = now
    
    # Check limits
    if limit.requests_per_minute >= config.rate_limit_per_minute:
        return False
    if limit.requests_per_hour >= config.rate_limit_per_hour:
        return False
    
    # Increment counters
    limit.requests_per_minute += 1
    limit.requests_per_hour += 1
    limit.tenant_id = tenant_id
    
    return True


def check_rbac(tenant_id: str, config: TenantConfig, route: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Check RBAC rules for tenant."""
    # Check if route is allowed
    if route and route not in config.allowed_routes:
        return False, f"Route {route} not allowed for tenant {tenant_id}"
    
    return True, None


def check_guardrails(tenant_id: str, config: TenantConfig, query: str) -> tuple[bool, Optional[str]]:
    """Check guardrails (sensitive prompts, refusal rules)."""
    query_lower = query.lower()
    
    # Check sensitive prompt patterns
    for pattern in config.sensitive_prompt_patterns:
        if pattern.lower() in query_lower:
            return False, f"Query matches sensitive pattern: {pattern}"
    
    # Check refusal rules
    for rule in config.refusal_rules:
        rule_type = rule.get("type")
        if rule_type == "contains" and rule.get("pattern", "").lower() in query_lower:
            return False, rule.get("reason", "Query violates refusal rule")
    
    return True, None


@app.get("/")
async def root():
    """Serve chat UI if static files exist."""
    ui_path = static_dir / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return {"message": "Multi-Tenant Request Router. Use POST /chat or add static/index.html for UI."}


@app.post("/chat")
async def route_chat(
    request: Request,
    payload: MultiTenantChatRequest,
    x_tenant_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Route chat request with tenant isolation."""
    start_time = time.time()
    
    # Extract tenant_id (default to t1 for UI / simple testing)
    tenant_id = x_tenant_id or payload.tenant_id
    if not tenant_id:
        try:
            tenant_id = get_tenant_id_from_jwt(authorization, x_tenant_id)
        except HTTPException:
            tenant_id = "t1"
    
    # Get tenant config (in production, from database/Secrets Manager)
    config = TENANT_CONFIGS.get(tenant_id)
    if not config:
        config = TenantConfig(
            tenant_id=tenant_id,
            rate_limit_per_minute=10,
            rate_limit_per_hour=100,
        )
        TENANT_CONFIGS[tenant_id] = config
    
    # Check rate limits
    if not check_rate_limit(tenant_id, config):
        logger.warning(f"Rate limit exceeded for tenant {tenant_id}")
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
        )
    
    # Check guardrails
    guardrail_ok, guardrail_reason = check_guardrails(tenant_id, config, payload.query)
    if not guardrail_ok:
        logger.warning(f"Guardrail violation for tenant {tenant_id}: {guardrail_reason}")
        from src.app.schemas import ChatResponse, Refusal
        return ChatResponse.refused(
            route="CLARIFY",
            reason=guardrail_reason or "Query violates guardrails",
        )
    
    # Forward to orchestrator
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/chat",
                json={
                    **payload.dict(),
                    "tenant_id": tenant_id,
                },
            )
            response.raise_for_status()
            try:
                result = response.json()
            except Exception as e:
                logger.error("Orchestrator response not valid JSON: %s", e)
                raise HTTPException(status_code=502, detail="Orchestrator returned invalid response")
            citations = result.get("citations") or []
            refusal = result.get("refusal") or {}
            meta = result.get("meta") or {}
            latency_ms = int((time.time() - start_time) * 1000)
            metrics = TenantMetrics(
                tenant_id=tenant_id,
                route=result.get("route", "UNKNOWN"),
                latency_ms=latency_ms,
                chunk_ids=[(c.get("ref") if isinstance(c, dict) else "") for c in citations],
                citations=citations,
                refusal_reason=refusal.get("reason") if isinstance(refusal, dict) else None,
                token_usage=meta.get("token_usage") if isinstance(meta.get("token_usage"), dict) else {},
                cost_usd_estimate=meta.get("cost_usd_estimate", 0.0) if isinstance(meta.get("cost_usd_estimate"), (int, float)) else 0.0,
            )
            emit_metrics(metrics)
            log_request(tenant_id, payload.query, result.get("route"), latency_ms)
            
            return result
    except httpx.HTTPError as e:
        logger.error(f"Orchestrator request failed: {e}")
        raise HTTPException(status_code=502, detail="Orchestrator service unavailable")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "request-router"}


@app.get("/tenant/{tenant_id}/config")
def get_tenant_config(tenant_id: str):
    """Get tenant configuration (admin endpoint)."""
    config = TENANT_CONFIGS.get(tenant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return config


@app.put("/tenant/{tenant_id}/config")
def update_tenant_config(tenant_id: str, config: TenantConfig):
    """Update tenant configuration (admin endpoint)."""
    TENANT_CONFIGS[tenant_id] = config
    return {"status": "updated"}

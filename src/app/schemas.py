from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    model_config = {"extra": "ignore"}  # allow tenant_id from router

    user_id: str
    session_id: str
    query: str
    locale: str | None = "en-IN"


class IntentEntities(BaseModel):
    product: Optional[str] = None
    ticker: Optional[str] = None
    food: Optional[str] = None
    budget: Optional[str] = None
    location: Optional[str] = None


class IntentPrediction(BaseModel):
    route: str = Field(..., pattern="^(PRICE_COMPARE|FINANCE_STOCK|DIET_NUTRITION|CLARIFY|GENERAL_QUERY)$")
    confidence: float = Field(..., ge=0, le=1)
    clarifying_question: Optional[str] = None
    extracted_entities: Optional[IntentEntities] = None


class Citation(BaseModel):
    type: str
    ref: str
    details: Optional[str] = None


class ToolCallLog(BaseModel):
    tool_name: str
    status: str
    error: Optional[str] = None


class Refusal(BaseModel):
    is_refused: bool = False
    reason: Optional[str] = None


class TokenUsage(BaseModel):
    prompt: int = 0
    completion: int = 0
    total: int = 0


class Meta(BaseModel):
    latency_ms: int = 0
    token_usage: TokenUsage = TokenUsage()
    cost_usd_estimate: float = 0.0


class ChatResponse(BaseModel):
    route: str
    answer: str
    citations: List[Citation] = []
    tool_calls: List[ToolCallLog] = []
    refusal: Refusal = Refusal()
    meta: Meta = Meta()

    @classmethod
    def refused(cls, route: str, reason: str) -> "ChatResponse":
        return cls(
            route=route,
            answer="",
            citations=[],
            tool_calls=[],
            refusal=Refusal(is_refused=True, reason=reason),
        )


class VaultChunk(BaseModel):
    user_id: str
    chunk_id: str
    text: str
    source: str = "user_vault"
    confidence_score: float | None = None  # Similarity score from retrieval (0-1)
    retrieval_method: str = "similarity_search"  # Method used: similarity_search, mmr, reranked


class PriceItem(BaseModel):
    product_id: str
    name: str
    price: float
    currency: str
    vendor: str
    location: str
    source: str


class PriceComparisonResult(BaseModel):
    items: List[PriceItem]
    summary: str


class Quote(BaseModel):
    ticker: str
    price: float
    currency: str
    change_pct: float
    source: str


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    summary: str

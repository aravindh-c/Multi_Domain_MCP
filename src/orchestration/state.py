"""LangGraph state schema for conversation workflow."""
from typing import Any, Dict, List, Optional, TypedDict

from src.app.schemas import ChatRequest, IntentPrediction, VaultChunk


class ConversationState(TypedDict):
    """State schema for the LangGraph conversation workflow."""

    # Input
    request: ChatRequest

    # Intent classification
    intent: Optional[IntentPrediction]
    route: Optional[str]  # PRICE_COMPARE | FINANCE_STOCK | DIET_NUTRITION | CLARIFY

    # Tool results
    price_result: Optional[Any]  # ComparisonResult from price MCP
    finance_quote: Optional[Any]  # Quote from finance MCP
    finance_history: Optional[List[Any]]  # List[Candle] from finance MCP
    finance_news: Optional[List[Any]]  # List[NewsItem] from finance MCP

    # RAG vault retrieval (diet route only)
    vault_chunks: Optional[List[VaultChunk]]
    retrieval_error: Optional[str]  # Error from retrieval step
    generation_error: Optional[str]  # Error from generation step
    retrieval_confidence_avg: Optional[float]  # Average confidence of retrieved chunks

    # Output
    answer: Optional[str]
    citations: Optional[List[Dict[str, str]]]
    tool_calls: Optional[List[Dict[str, Any]]]
    refusal: Optional[str]

    # Metadata
    meta: Optional[Dict[str, Any]]

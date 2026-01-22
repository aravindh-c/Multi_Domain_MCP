import logging
import re
from typing import Any, Dict

from pydantic import ValidationError

from src.app.schemas import Candle, NewsItem, Quote
from src.tools.mcp_client import finance_bundle, finance_top_gainers

logger = logging.getLogger(__name__)


def _is_market_wide_query(query: str) -> bool:
    """Detect if query asks for market-wide data (top gainers, losers, etc.)"""
    lower = query.lower()
    market_patterns = [
        r"top\s+\d+\s+gainers?",
        r"top\s+gainers?",
        r"top\s+\d+\s+losers?",
        r"top\s+losers?",
        r"market\s+leaders?",
        r"best\s+performing\s+stocks?",
    ]
    return any(re.search(pattern, lower) for pattern in market_patterns)


def _is_general_knowledge_query(query: str) -> bool:
    """
    Detect if query is asking for general finance knowledge that LLM can answer
    without needing live data or specific tools.
    """
    lower = query.lower()
    knowledge_patterns = [
        r"what\s+is\s+(a\s+)?(p/e|pe|price.*earnings?|dividend|beta|roe|roce)",
        r"how\s+does\s+(the\s+)?(stock\s+)?market\s+work",
        r"explain\s+(p/e|pe|dividend|beta|roe|roce|stock\s+market)",
        r"difference\s+between\s+(nse|bse|nifty|sensex)",
        r"what\s+is\s+(nse|bse|nifty|sensex)",
        r"how\s+to\s+calculate\s+(return|profit|loss)",
        r"what\s+does\s+(p/e|pe|dividend|beta|roe|roce)\s+mean",
    ]
    return any(re.search(pattern, lower) for pattern in knowledge_patterns)


def _is_calculation_query(query: str) -> bool:
    """Detect if query is asking for a calculation that LLM can do."""
    lower = query.lower()
    calc_patterns = [
        r"calculate\s+(return|profit|loss|gain)",
        r"what\s+(is|would\s+be)\s+(my\s+)?(return|profit|loss)",
        r"if\s+i\s+(bought|purchased|invested)",
        r"how\s+much\s+(profit|loss|return)",
    ]
    return any(re.search(pattern, lower) for pattern in calc_patterns)


def mcp_finance_node(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state["request"].query
    
    # Strategy: Classify query type and handle accordingly
    # 1. General knowledge → Skip tools, let LLM answer directly
    if _is_general_knowledge_query(query) or _is_calculation_query(query):
        # Mark that we're using LLM directly (no tools needed)
        state["finance_use_llm_directly"] = True
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({
            "tool_name": "mcp_finance.llm_fallback",
            "status": "skipped",
            "reason": "General knowledge/calculation query - using LLM directly"
        })
        return state
    
    # 2. Market-wide data → Try tool, refuse if unavailable
    if _is_market_wide_query(query):
        # Try to get top gainers
        limit_match = re.search(r"top\s+(\d+)", query.lower())
        limit = int(limit_match.group(1)) if limit_match else 5
        
        top_gainers = finance_top_gainers(limit=limit)
        if top_gainers is None:
            # Feature not available - set refusal
            state["refusal"] = (
                "I cannot provide top gainers data at this time. "
                "This feature requires market-wide data scraping from Screener.in or an alternative data source, "
                "which is not yet implemented. Please ask about a specific stock ticker instead."
            )
            if state.get("tool_calls") is None:
                state["tool_calls"] = []
            state["tool_calls"].append({
                "tool_name": "mcp_finance.top_gainers",
                "status": "unavailable",
                "error": "Feature not implemented"
            })
            return state
        
        # If we got data, store it (for future use in generation)
        state["finance_top_gainers"] = top_gainers
        if state.get("citations") is None:
            state["citations"] = []
        state["citations"].append({"type": "tool", "ref": top_gainers.get("source", "mcp_finance_server")})
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({"tool_name": "mcp_finance.top_gainers", "status": "ok"})
        return state
    
    # Single ticker query - existing logic
    intent = state.get("intent")
    ticker = intent.extracted_entities.ticker if intent and intent.extracted_entities else None
    
    # Only use ticker if we can extract one; otherwise refuse
    if not ticker:
        # Try to extract ticker from query (simple heuristic)
        words = query.upper().split()
        # Look for common ticker patterns (3-5 letter codes)
        potential_tickers = [w for w in words if 3 <= len(w) <= 5 and w.isalpha()]
        if not potential_tickers:
            state["refusal"] = (
                "I need a specific stock ticker to provide finance data. "
                "Please specify a stock symbol (e.g., 'TCS', 'RELIANCE', 'INFY'). "
                "For market-wide queries like 'top gainers', that feature is not yet available."
            )
            if state.get("tool_calls") is None:
                state["tool_calls"] = []
            state["tool_calls"].append({
                "tool_name": "mcp_finance.bundle",
                "status": "error",
                "error": "No ticker provided in query"
            })
            return state
        ticker = potential_tickers[0]
    
    try:
        raw = finance_bundle(ticker=ticker)
        state["finance_quote"] = Quote(**raw["quote"])
        state["finance_history"] = [Candle(**c) for c in raw.get("history", [])]
        state["finance_news"] = [NewsItem(**n) for n in raw.get("news", [])]
        if state.get("citations") is None:
            state["citations"] = []
        state["citations"].append({"type": "tool", "ref": raw["quote"]["source"]})
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({"tool_name": "mcp_finance.bundle", "status": "ok"})
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        logger.error("Finance tool failed: %s", exc)
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({"tool_name": "mcp_finance.bundle", "status": "error", "error": str(exc)})
    return state

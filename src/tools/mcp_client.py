import logging
from typing import Any, Dict, List

import httpx

from src.app.settings import settings

logger = logging.getLogger(__name__)


def _post(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=settings.request_timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("MCP call failed for %s: %s", url, exc)
        raise


def price_compare(query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{settings.mcp_price_server_url}/compare"
    return _post(url, {"query": query, "filters": filters})


def finance_bundle(ticker: str, period: str = "1mo", news_limit: int = 5) -> Dict[str, Any]:
    url = f"{settings.mcp_finance_server_url}/bundle"
    return _post(url, {"ticker": ticker, "period": period, "news_limit": news_limit})


def finance_top_gainers(limit: int = 5) -> Dict[str, Any] | None:
    """Get top gainers from finance MCP. Returns None if feature unavailable."""
    url = f"{settings.mcp_finance_server_url}/top-gainers"
    try:
        return _post(url, {"limit": limit})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Top gainers not available: %s", exc)
        return None

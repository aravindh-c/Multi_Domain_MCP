import logging
from typing import Any, Dict

from pydantic import ValidationError

from src.app.schemas import PriceComparisonResult
from src.tools.mcp_client import price_compare

logger = logging.getLogger(__name__)


def mcp_price_node(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state["request"].query
    filters = {}
    try:
        raw = price_compare(query=query, filters=filters)
        result = PriceComparisonResult(**raw)
        state["price_result"] = result
        if state.get("citations") is None:
            state["citations"] = []
        state["citations"].extend([{"type": "tool", "ref": item.source} for item in result.items])
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({"tool_name": "mcp_price.compare", "status": "ok"})
    except (ValidationError, Exception) as exc:  # noqa: BLE001
        logger.error("Price tool failed: %s", exc)
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({"tool_name": "mcp_price.compare", "status": "error", "error": str(exc)})
    return state

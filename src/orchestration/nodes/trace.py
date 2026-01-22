import logging
import time

from src.app.schemas import ChatResponse

logger = logging.getLogger(__name__)


def trace_node(state):
    start = state.get("meta", {}).get("start_time_ms")
    if start:
        latency = int(time.time() * 1000 - start)
    else:
        latency = 0
    state.setdefault("meta", {})["latency_ms"] = latency
    logger.info(
        "route=%s latency_ms=%s tool_calls=%s citations=%s",
        state.get("route"),
        latency,
        len(state.get("tool_calls", [])),
        len(state.get("citations", [])),
    )
    return state

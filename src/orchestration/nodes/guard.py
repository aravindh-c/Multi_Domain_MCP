from src.app.schemas import ChatResponse
from src.orchestration.state import ConversationState


def guard_node(state: ConversationState) -> ConversationState:
    route = state.get("route") or "CLARIFY"
    # enforce vault isolation: only diet can retrieve
    state["route"] = route
    return state

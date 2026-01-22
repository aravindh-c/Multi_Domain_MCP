from src.app.schemas import ChatRequest
from src.orchestration.state import ConversationState


def intake_node(state: ConversationState) -> ConversationState:
    # State already seeded in API layer; keep for symmetry/future validation.
    req: ChatRequest = state["request"]
    state["meta"] = state.get("meta", {})
    state["meta"]["user_id"] = req.user_id
    state["meta"]["session_id"] = req.session_id
    return state

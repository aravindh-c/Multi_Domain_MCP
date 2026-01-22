from langgraph.graph import END, StateGraph

from src.orchestration.state import ConversationState
from src.orchestration.nodes.intake import intake_node
from src.orchestration.nodes.intent import intent_node
from src.orchestration.nodes.guard import guard_node
from src.orchestration.nodes.vault_retrieve import vault_retrieve_node
from src.orchestration.nodes.mcp_price import mcp_price_node
from src.orchestration.nodes.mcp_finance import mcp_finance_node
from src.orchestration.nodes.generate import generate_node
from src.orchestration.nodes.trace import trace_node


def build_workflow():
    graph = StateGraph(ConversationState)

    graph.add_node("intake", intake_node)
    graph.add_node("classify_intent", intent_node)
    graph.add_node("guard", guard_node)
    graph.add_node("vault_retrieve", vault_retrieve_node)
    graph.add_node("mcp_price", mcp_price_node)
    graph.add_node("mcp_finance", mcp_finance_node)
    graph.add_node("generate", generate_node)
    graph.add_node("trace", trace_node)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "classify_intent")
    graph.add_edge("classify_intent", "guard")

    # Conditional routing
    graph.add_conditional_edges(
        "guard",
        lambda state: state.get("route"),
        {
            "DIET_NUTRITION": "vault_retrieve",
            "PRICE_COMPARE": "mcp_price",
            "FINANCE_STOCK": "mcp_finance",
            "CLARIFY": "generate",
        },
    )

    graph.add_edge("vault_retrieve", "generate")
    graph.add_edge("mcp_price", "generate")
    graph.add_edge("mcp_finance", "generate")
    graph.add_edge("generate", "trace")
    graph.add_edge("trace", END)

    # Older langgraph versions do not support max_cycles kwarg on compile.
    compiled = graph.compile()
    return compiled

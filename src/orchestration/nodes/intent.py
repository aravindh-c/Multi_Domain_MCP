import json
import logging
from typing import Any, Dict

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import RateLimitError

from src.app.schemas import IntentPrediction
from src.app.settings import settings
from src.prompts.intent_prompt import INTENT_SYSTEM, INTENT_USER_TEMPLATE
from src.tools.openai_retry import retry_with_backoff

logger = logging.getLogger(__name__)


def _build_chain():
    parser = PydanticOutputParser(pydantic_object=IntentPrediction)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", INTENT_SYSTEM),
            ("user", INTENT_USER_TEMPLATE + "\nReturn JSON only.\n{format_instructions}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    # IMPORTANT: only pass api_key if it is set, otherwise let langchain-openai
    # resolve OPENAI_API_KEY from the environment.
    llm_kwargs: Dict[str, Any] = {
        "model": settings.model_name,
        "temperature": 0,
        "timeout": settings.request_timeout,
    }
    if settings.openai_api_key:
        llm_kwargs["api_key"] = settings.openai_api_key

    llm = ChatOpenAI(**llm_kwargs)
    return prompt | llm | parser


@retry_with_backoff(max_retries=3, initial_delay=1.0, max_delay=30.0)
def _invoke_with_retry(chain, inputs: Dict[str, Any]) -> IntentPrediction:
    """Invoke chain with retry logic for rate limits."""
    return chain.invoke(inputs)


def _fallback_intent(query: str) -> IntentPrediction:
    lower = query.lower()
    if any(k in lower for k in ["price", "buy", "compare", "cost", "rs", "budget"]):
        route = "PRICE_COMPARE"
    elif any(k in lower for k in ["stock", "ticker", "market", "share", "finance"]):
        route = "FINANCE_STOCK"
    elif any(k in lower for k in ["diet", "eat", "food", "calorie", "protein", "good for me", "paneer"]):
        route = "DIET_NUTRITION"
    else:
        # No specific domain identified -> general query (LLM answer with caution)
        route = "GENERAL_QUERY"
    return IntentPrediction(route=route, confidence=0.4, clarifying_question=None, extracted_entities=None)


def intent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state["request"].query
    locale = state["request"].locale
    try:
        chain = _build_chain()
        prediction: IntentPrediction = _invoke_with_retry(chain, {"query": query, "locale": locale})
    except RateLimitError as e:
        error_msg = str(e)
        if "insufficient_quota" in error_msg.lower():
            logger.error(
                "OpenAI quota/rate limit exceeded. "
                "Check your billing plan and spending limits. Error: %s",
                error_msg,
            )
        else:
            logger.error("OpenAI rate limit error: %s", error_msg)
        logger.info("Falling back to heuristic intent classifier")
        prediction = _fallback_intent(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Intent chain failed, using fallback: %s", exc)
        prediction = _fallback_intent(query)

    state["intent"] = prediction
    # When classifier says CLARIFY (no specific domain), route to GENERAL_QUERY for LLM answer with caution
    state["route"] = "GENERAL_QUERY" if prediction.route == "CLARIFY" else prediction.route
    if state.get("tool_calls") is None:
        state["tool_calls"] = []
    state["tool_calls"].append({"tool_name": "intent_classifier", "status": "ok"})
    return state

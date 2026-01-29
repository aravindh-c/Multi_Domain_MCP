import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import RateLimitError

from src.app.schemas import ChatResponse
from src.app.settings import settings
from src.prompts.diet_prompt import DIET_SYSTEM, DIET_USER_TEMPLATE
from src.prompts.finance_prompt import FINANCE_SYSTEM, FINANCE_USER_TEMPLATE
from src.prompts.price_prompt import PRICE_SYSTEM, PRICE_USER_TEMPLATE
from src.tools.openai_retry import retry_with_backoff

logger = logging.getLogger(__name__)


def _llm():
    # IMPORTANT: only pass api_key if it is set, otherwise let langchain-openai
    # resolve OPENAI_API_KEY from the environment.
    kwargs: Dict[str, Any] = {
        "model": settings.model_name,
        "temperature": 0.2,
        "timeout": settings.request_timeout,
    }
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    return ChatOpenAI(**kwargs)


@retry_with_backoff(max_retries=3, initial_delay=1.0, max_delay=30.0)
def _invoke_llm_with_retry(llm: ChatOpenAI, messages: list) -> str:
    """Invoke LLM with retry logic for rate limits."""
    response = llm.invoke(messages)
    return response.content


def _render_price(state: Dict[str, Any]) -> str:
    result = state.get("price_result")
    if not result:
        return "Price comparison unavailable right now."
    lines = []
    for item in result.items:
        lines.append(f"{item.name}: {item.price} {item.currency} at {item.vendor} ({item.location}) source={item.source}")
    return "\n".join(lines) + f"\nSummary: {result.summary}"


def _render_history(history):
    if not history:
        return "No history data"
    return "; ".join([f"{c.date}: close {c.close}" for c in history[:5]])


def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    route = state.get("route", "CLARIFY")
    query = state["request"].query

    if route == "CLARIFY":
        intent = state.get("intent")
        question = (intent.clarifying_question if intent else None) or "Could you provide more specifics? What would you like help with? (e.g. price comparison, stocks, or diet/nutrition)"
        state["answer"] = question
        return state

    if route == "GENERAL_QUERY":
        # No specific domain identified: answer with LLM and caution message
        caution = "This is general information only. Not financial, medical, or purchasing advice.\n\n"
        try:
            llm = _llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant. Answer the user's question concisely and accurately. Do not give financial, medical, or purchasing advice."),
                ("user", "{query}"),
            ])
            msg = prompt.format_messages(query=query)
            answer = _invoke_llm_with_retry(llm, msg)
            state["answer"] = caution + answer
        except Exception as exc:
            logger.exception("General query generation failed: %s", exc)
            state["answer"] = caution + "I couldn't generate a response right now. Please try again."
        return state

    # Clear generation error
    state["generation_error"] = None
    
    try:
        llm = _llm()
        if route == "DIET_NUTRITION":
            # Check for retrieval errors first
            retrieval_error = state.get("retrieval_error")
            if retrieval_error:
                logger.error(f"Retrieval error detected: {retrieval_error}")
                state["answer"] = (
                    f"I encountered an error retrieving your medical information: {retrieval_error}. "
                    "Please try again or contact support."
                )
                return state
            
            vault_chunks = state.get("vault_chunks", [])
            retrieval_confidence = state.get("retrieval_confidence_avg")
            
            # Check if retrieval confidence is too low
            if retrieval_confidence is not None and retrieval_confidence < settings.min_retrieval_confidence:
                logger.warning(f"Low retrieval confidence: {retrieval_confidence:.3f}")
                state["answer"] = (
                    "I couldn't find highly relevant information in your medical records for this query. "
                    "The retrieved information may not be accurate. Please consult your doctor for personalized advice."
                )
                return state
            
            if not vault_chunks:
                logger.warning("No vault chunks retrieved")
                state["answer"] = (
                    "I couldn't retrieve relevant information from your medical records. "
                    "Please ensure your vault has been ingested, or try rephrasing your question."
                )
                return state
            
            vault_ctx = "\n---\n".join([chunk.text for chunk in vault_chunks]) or "No context found."
            logger.info(f"Using {len(vault_chunks)} chunks for generation, avg_confidence: {retrieval_confidence:.3f if retrieval_confidence else 'N/A'}")
            
            prompt = ChatPromptTemplate.from_messages(
                [("system", DIET_SYSTEM), ("user", DIET_USER_TEMPLATE)]
            )
            msg = prompt.format_messages(query=query, vault_context=vault_ctx)
            answer = _invoke_llm_with_retry(llm, msg) + "\n\nCaution: For personal medical advice, consult your doctor."
        elif route == "PRICE_COMPARE":
            prompt = ChatPromptTemplate.from_messages([("system", PRICE_SYSTEM), ("user", PRICE_USER_TEMPLATE)])
            msg = prompt.format_messages(query=query, price_data=_render_price(state))
            answer = _invoke_llm_with_retry(llm, msg)
        elif route == "FINANCE_STOCK":
            # Check if we have a refusal reason (e.g., top gainers not available)
            refusal = state.get("refusal")
            if refusal:
                state["answer"] = refusal
                return state
            
            # Check if this is a general knowledge query (use LLM directly)
            if state.get("finance_use_llm_directly"):
                # LLM can answer general finance questions without tools
                # Add transparency message that this is general knowledge, not tool-sourced
                transparency_prefix = (
                    "I don't have access to real-time market data or specific tools for this query, "
                    "but I can provide general information based on finance knowledge:\n\n"
                )
                general_finance_prompt = ChatPromptTemplate.from_messages([
                    ("system", "You are a helpful finance educator. Explain finance concepts clearly and accurately. Always add 'Not financial advice.' at the end."),
                    ("user", "{query}")
                ])
                msg = general_finance_prompt.format_messages(query=query)
                llm_answer = _invoke_llm_with_retry(llm, msg)
                answer = transparency_prefix + llm_answer + "\n\nNot financial advice."
            else:
                # Tool-based queries
                quote = state.get("finance_quote")
                history = state.get("finance_history")
                news = state.get("finance_news")
                top_gainers = state.get("finance_top_gainers")
                
                if top_gainers:
                    # Handle top gainers response
                    stocks = top_gainers.get("stocks", [])
                    answer = f"Top {len(stocks)} Gainers:\n\n"
                    for i, stock in enumerate(stocks, 1):
                        answer += f"{i}. {stock.get('name', stock.get('ticker', 'N/A'))} ({stock.get('ticker', 'N/A')}): "
                        answer += f"₹{stock.get('price', 0):.2f} ({stock.get('change_pct', 0):+.2f}%)\n"
                    answer += f"\nSource: {top_gainers.get('source', 'mcp_finance_server')}\nNot financial advice."
                else:
                    # Single ticker response (only if we have quote data; otherwise refusal is set in mcp_finance_node)
                    if not quote:
                        state["answer"] = (
                            "I couldn't fetch stock data for this ticker. "
                            "The finance data service is not available in this environment. "
                            "You can ask general finance questions instead."
                        )
                        return state
                    history_str = _render_history(history) if history else "No historical data available"
                    news_list = [n.dict() for n in news] if news else []
                    prompt = ChatPromptTemplate.from_messages([("system", FINANCE_SYSTEM), ("user", FINANCE_USER_TEMPLATE)])
                    msg = prompt.format_messages(
                        ticker=quote.ticker,
                        quote=quote.dict(),
                        history=history_str,
                        news=news_list,
                    )
                    answer = _invoke_llm_with_retry(llm, msg) + "\nNot financial advice."
        else:
            answer = "Unable to generate response for this route."
    except RateLimitError as e:
        error_msg = str(e)
        state["generation_error"] = f"rate_limit: {error_msg}"
        if "insufficient_quota" in error_msg.lower():
            logger.error(
                "OpenAI quota/rate limit exceeded. "
                "Check your billing plan and spending limits. Error: %s",
                error_msg,
            )
            answer = (
                "I'm currently experiencing rate limit issues with the AI service. "
                "This may be due to billing/quota limits. Please check your OpenAI account settings "
                "or try again in a few minutes."
            )
        else:
            logger.error("OpenAI rate limit error: %s", error_msg)
            answer = "Rate limit exceeded. Please try again in a moment."
    except Exception as exc:  # noqa: BLE001
        state["generation_error"] = str(exc)
        logger.error("LLM generation failed: %s", exc, exc_info=True)
        answer = "Response generation failed; please try again."

    state["answer"] = answer
    return state

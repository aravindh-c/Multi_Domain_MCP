import logging
import os
import time
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from src.app.logging import configure_logging
from src.app.schemas import ChatRequest, ChatResponse
from src.app.settings import settings
from src.observability.langsmith import configure_tracing
from src.observability.metrics import build_meta
from src.orchestration.graph import build_workflow

configure_logging()
configure_tracing()

app = FastAPI(title="Multi-Domain Tool-First Chatbot")


@app.on_event("startup")
def load_secrets_from_aws():
    """When running in AWS, load OPENAI_API_KEY and LANGSMITH_API_KEY from Secrets Manager if not in env."""
    if not os.environ.get("SECRETS_MANAGER_SECRET_NAME"):
        return
    try:
        from src.app.aws_settings import aws_settings
        if not os.environ.get("OPENAI_API_KEY"):
            key = aws_settings.get_openai_api_key()
            if key:
                os.environ["OPENAI_API_KEY"] = key
                settings.openai_api_key = key
                logging.getLogger(__name__).info("Loaded OPENAI_API_KEY from Secrets Manager")
        if not os.environ.get("LANGSMITH_API_KEY"):
            ls_key = aws_settings.get_langsmith_api_key()
            if ls_key:
                os.environ["LANGSMITH_API_KEY"] = ls_key
                logging.getLogger(__name__).info("Loaded LANGSMITH_API_KEY from Secrets Manager")
    except Exception as e:
        logging.getLogger(__name__).warning("Could not load secrets from Secrets Manager: %s", e)

# Serve static files (chat UI)
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
workflow = build_workflow()
logger = logging.getLogger(__name__)


def get_workflow():
    return workflow


@app.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    wf=Depends(get_workflow),
):
    start = int(time.time() * 1000)
    try:
        state = {
            "request": payload,
            "meta": {"start_time_ms": start},
            "citations": [],
            "tool_calls": [],
        }
        result = wf.invoke(state)
        answer = result.get("answer", "")
        route = result.get("route", "CLARIFY")
        citations = result.get("citations", [])
        tool_calls = result.get("tool_calls", [])
        refusal_reason = result.get("refusal")
        retrieval_error = result.get("retrieval_error")
        generation_error = result.get("generation_error")
        retrieval_confidence = result.get("retrieval_confidence_avg")
        meta = build_meta(latency_ms=result.get("meta", {}).get("latency_ms", 0))
        
        # Log error attribution for debugging
        if retrieval_error:
            logger.warning(f"Retrieval error: {retrieval_error}")
        if generation_error:
            logger.warning(f"Generation error: {generation_error}")
        if retrieval_confidence is not None:
            logger.info(f"Retrieval confidence: {retrieval_confidence:.3f}")
        
        if route == "CLARIFY":
            meta.latency_ms = int(time.time() * 1000 - start)
        response = ChatResponse(
            route=route,
            answer=answer,
            citations=citations,
            tool_calls=tool_calls,
            refusal={"is_refused": bool(refusal_reason), "reason": refusal_reason} if refusal_reason else {"is_refused": False, "reason": None},
            meta=meta,
        )
        return response
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat handler failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/vault/{user_id}")
def debug_vault(user_id: str, query: str = "user medical constraints and diet considerations"):
    """Debug endpoint to view retrieved chunks for a user."""
    from src.rag.retriever import retrieve_for_user
    
    chunks, avg_confidence = retrieve_for_user(user_id=user_id, query=query, top_k=10)  # Get more for debugging
    
    return {
        "user_id": user_id,
        "query": query,
        "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text[:200] + "..." if len(chunk.text) > 200 else chunk.text,  # Preview
                "text_length": len(chunk.text),
                "source": chunk.source,
                "confidence_score": round(chunk.confidence_score, 3) if chunk.confidence_score is not None else None,
                "retrieval_method": chunk.retrieval_method,
            }
            for chunk in chunks
        ],
        "total_chunks": len(chunks),
    }


@app.get("/")
async def root():
    """Redirect to chat UI."""
    from fastapi.responses import FileResponse
    ui_path = static_dir / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    return {"message": "Chat UI not found. Use POST /chat endpoint."}

import logging

from src.app.settings import settings
from src.rag.retriever import retrieve_for_user
from src.orchestration.state import ConversationState

logger = logging.getLogger(__name__)


def vault_retrieve_node(state: ConversationState) -> ConversationState:
    """Retrieve vault chunks with improved RAG techniques and error attribution."""
    user_id = state["request"].user_id
    query = state["request"].query  # Use actual user query instead of fixed string
    
    # Clear any previous retrieval errors
    state["retrieval_error"] = None
    state["retrieval_confidence_avg"] = None
    
    try:
        chunks, avg_confidence = retrieve_for_user(
            user_id=user_id,
            query=query,  # Pass actual query
            top_k=settings.diet_top_k,
        )
        
        state["vault_chunks"] = chunks
        state["retrieval_confidence_avg"] = avg_confidence
        
        # Add citations with confidence scores
        if state.get("citations") is None:
            state["citations"] = []
        for chunk in chunks:
            citation = {
                "type": "user_vault",
                "ref": f"chunk:{user_id}:{chunk.chunk_id}",
            }
            if chunk.confidence_score is not None:
                citation["confidence"] = round(chunk.confidence_score, 3)
            if chunk.retrieval_method:
                citation["method"] = chunk.retrieval_method
            state["citations"].append(citation)
        
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        
        # Log retrieval method and confidence
        method = chunks[0].retrieval_method if chunks else "none"
        state["tool_calls"].append({
            "tool_name": "diet_vault_retriever",
            "status": "ok",
            "chunks_retrieved": len(chunks),
            "avg_confidence": round(avg_confidence, 3) if avg_confidence else None,
            "method": method,
        })
        
        # Check if confidence is too low
        if avg_confidence is not None and avg_confidence < settings.min_retrieval_confidence:
            logger.warning(f"Low retrieval confidence: {avg_confidence:.3f} < {settings.min_retrieval_confidence}")
        
    except Exception as exc:
        logger.error(f"Vault retrieval failed: {exc}", exc_info=True)
        state["retrieval_error"] = str(exc)
        state["vault_chunks"] = []
        if state.get("tool_calls") is None:
            state["tool_calls"] = []
        state["tool_calls"].append({
            "tool_name": "diet_vault_retriever",
            "status": "error",
            "error": str(exc),
        })
    
    return state

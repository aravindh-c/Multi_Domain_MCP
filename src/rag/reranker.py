"""Reranking utilities for retrieved documents."""
import logging
from typing import List

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Try to import sentence-transformers for reranking
try:
    from sentence_transformers import CrossEncoder
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    logger.warning("sentence-transformers not installed. Reranking disabled. Install with: pip install sentence-transformers")


def rerank_documents(query: str, documents: List[Document], top_n: int = 4) -> List[tuple[Document, float]]:
    """
    Rerank documents using a cross-encoder for better precision.
    
    Args:
        query: User query
        documents: List of retrieved documents
        top_n: Number of top documents to return
    
    Returns:
        List of (document, score) tuples, sorted by score (highest first)
    """
    if not RERANKER_AVAILABLE:
        logger.warning("Reranking requested but sentence-transformers not available. Returning original order.")
        return [(doc, 1.0) for doc in documents[:top_n]]
    
    if not documents:
        return []
    
    try:
        # Use a lightweight cross-encoder model (good balance of speed/accuracy)
        # Alternative: "cross-encoder/ms-marco-MiniLM-L-6-v2" for faster but less accurate
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2", max_length=512)
        
        # Prepare pairs for scoring
        pairs = [[query, doc.page_content[:500]] for doc in documents]  # Truncate long docs
        
        # Score all pairs
        scores = model.predict(pairs)
        
        # Combine documents with scores and sort
        doc_scores = list(zip(documents, scores.tolist()))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Reranked {len(documents)} documents, returning top {top_n}")
        return doc_scores[:top_n]
    except Exception as exc:
        logger.error(f"Reranking failed: {exc}. Returning original order.")
        return [(doc, 1.0) for doc in documents[:top_n]]

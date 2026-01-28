"""Tenant-aware RAG retriever with namespace isolation."""
import logging
import pathlib
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from src.app.multi_tenant_schemas import MultiTenantVaultChunk
from src.app.settings import settings
from src.rag.logger import log_method_entry
from src.rag.reranker import rerank_documents

logger = logging.getLogger(__name__)


@log_method_entry(run_type="query")
def _load_vectorstore():
    """Load FAISS vectorstore."""
    path = pathlib.Path(settings.faiss_path)
    embeddings = OpenAIEmbeddings(model=settings.embedding_model, timeout=settings.request_timeout)
    if not path.exists():
        return None
    return FAISS.load_local(path.as_posix(), embeddings, allow_dangerous_deserialization=True)


@log_method_entry(run_type="query")
def retrieve_for_tenant(
    tenant_id: str,
    user_id: str,
    query: str,
    top_k: int | None = None,
) -> tuple[List[MultiTenantVaultChunk], float | None]:
    """
    Retrieve chunks for a tenant/user with tenant namespace isolation.
    
    Args:
        tenant_id: Tenant identifier (enforced in metadata filter)
        user_id: User identifier (enforced in metadata filter)
        query: Search query
        top_k: Number of chunks to retrieve
    
    Returns:
        Tuple of (chunks, average_confidence_score)
    """
    from src.rag.logger import get_vault_logger
    
    logger = get_vault_logger(run_type="query")
    top_k = top_k or settings.diet_top_k
    logger.info(
        f"Retrieving chunks for tenant_id: {tenant_id}, user_id: {user_id}, "
        f"query: '{query[:50]}...', top_k: {top_k}"
    )
    
    vectorstore = _load_vectorstore()
    if vectorstore is None:
        logger.warning(f"Vectorstore not found at {settings.faiss_path}, returning empty chunks")
        return [], None
    
    logger.info("Vectorstore loaded successfully")
    
    # CRITICAL: Enforce tenant isolation via metadata filter
    # Both tenant_id and user_id must match
    metadata_filter = {
        "tenant_id": tenant_id,
        "user_id": user_id,
    }
    
    try:
        retrieval_method = "similarity_search"
        
        if settings.use_mmr:
            logger.info(f"Using MMR retrieval (fetch_k={settings.mmr_fetch_k}, lambda={settings.mmr_lambda_param})")
            # Use FAISS's built-in MMR search with tenant filter
            docs = vectorstore.max_marginal_relevance_search(
                query,
                k=top_k,
                fetch_k=settings.mmr_fetch_k,
                lambda_mult=settings.mmr_lambda_param,
                filter=metadata_filter,  # Tenant isolation enforced here
            )
            # Get scores via similarity search
            docs_with_scores = vectorstore.similarity_search_with_score(
                query,
                k=settings.mmr_fetch_k,
                filter=metadata_filter,  # Tenant isolation enforced here
            )
            # Create a map of chunk_id to score
            score_map = {}
            for doc, score in docs_with_scores:
                meta = doc.metadata or {}
                chunk_id = str(meta.get("chunk_id", ""))
                if chunk_id:
                    score_map[chunk_id] = score
            
            # Match MMR docs with scores using chunk_id
            scores = []
            for doc in docs:
                meta = doc.metadata or {}
                chunk_id = str(meta.get("chunk_id", ""))
                score = score_map.get(chunk_id, 0.7)
                scores.append(score)
            
            retrieval_method = "mmr"
            logger.info(f"Retrieved {len(docs)} documents via MMR (tenant: {tenant_id})")
        else:
            logger.info("Using standard similarity search")
            docs_with_scores = vectorstore.similarity_search_with_score(
                query,
                k=top_k,
                filter=metadata_filter,  # Tenant isolation enforced here
            )
            docs: List[Document] = [doc for doc, _ in docs_with_scores]
            scores: List[float] = [score for _, score in docs_with_scores]
            logger.info(f"Retrieved {len(docs)} documents with similarity scores (tenant: {tenant_id})")
        
        # Verify tenant isolation (defense in depth)
        for doc in docs:
            meta = doc.metadata or {}
            doc_tenant_id = meta.get("tenant_id")
            doc_user_id = meta.get("user_id")
            if doc_tenant_id != tenant_id or doc_user_id != user_id:
                logger.error(
                    f"TENANT ISOLATION VIOLATION: Expected tenant_id={tenant_id}, user_id={user_id}, "
                    f"got tenant_id={doc_tenant_id}, user_id={doc_user_id}"
                )
                # Remove violating document
                docs.remove(doc)
        
        # Rerank if enabled
        if settings.use_reranking and docs:
            logger.info(f"Reranking top {len(docs)} documents")
            reranked = rerank_documents(query, docs, top_n=settings.rerank_top_n)
            docs = [doc for doc, _ in reranked]
            scores = [score for _, score in reranked]
            retrieval_method = "reranked"
            logger.info(f"After reranking: {len(docs)} documents")
        
        # Filter by confidence threshold
        if settings.min_retrieval_confidence > 0:
            filtered_docs = []
            filtered_scores = []
            for doc, score in zip(docs, scores):
                similarity = max(0.0, 1.0 - abs(score)) if score < 1.0 else score
                if similarity >= settings.min_retrieval_confidence:
                    filtered_docs.append(doc)
                    filtered_scores.append(similarity)
                else:
                    logger.warning(f"Filtered out document with low confidence: {similarity:.3f}")
            docs = filtered_docs[:top_k]
            scores = filtered_scores[:top_k]
        
        # Calculate average confidence
        if scores:
            normalized_scores = [max(0.0, 1.0 - abs(s)) if s < 1.0 else s for s in scores]
            avg_confidence = sum(normalized_scores) / len(normalized_scores)
        else:
            avg_confidence = None
        
        # Convert to MultiTenantVaultChunk
        chunks: List[MultiTenantVaultChunk] = []
        for doc, score in zip(docs, scores):
            meta = doc.metadata or {}
            
            # Final tenant isolation check
            if meta.get("tenant_id") != tenant_id or meta.get("user_id") != user_id:
                logger.error(f"Skipping document with tenant mismatch: {meta}")
                continue
            
            confidence = max(0.0, 1.0 - abs(score)) if score < 1.0 else min(1.0, score)
            
            chunks.append(
                MultiTenantVaultChunk(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    chunk_id=str(meta.get("chunk_id")),
                    text=doc.page_content,
                    source=meta.get("source", "user_vault"),
                    confidence_score=confidence,
                    retrieval_method=retrieval_method,
                )
            )
        
        logger.info(
            f"Returning {len(chunks)} chunks for tenant_id: {tenant_id}, user_id: {user_id}, "
            f"avg_confidence: {avg_confidence:.3f if avg_confidence else 'N/A'}"
        )
        return chunks, avg_confidence
        
    except Exception as exc:
        logger.error(f"Retrieval failed for tenant {tenant_id}: {exc}", exc_info=True)
        raise

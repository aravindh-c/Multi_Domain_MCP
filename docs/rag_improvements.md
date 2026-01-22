# RAG Improvements Documentation

This document describes the RAG (Retrieval Augmented Generation) improvements implemented in the chatbot.

## Overview

The RAG system has been enhanced with the following features:

1. **Query-Based Retrieval**: Uses actual user queries instead of fixed strings
2. **MMR (Maximal Marginal Relevance)**: Adds diversity to retrieved chunks
3. **Reranking**: Optional reranking for improved precision
4. **Confidence Scores**: Tracks retrieval confidence for each chunk
5. **Error Attribution**: Distinguishes between retrieval and generation errors

## Configuration

All RAG improvements are configurable via environment variables or `.env` file:

```bash
# Enable MMR for diversity (default: True)
USE_MMR=true

# MMR parameters
MMR_FETCH_K=20          # Fetch more docs, then select diverse top_k
MMR_LAMBDA_PARAM=0.5    # 0 = max diversity, 1 = max relevance

# Enable reranking (default: False, requires sentence-transformers)
USE_RERANKING=false
RERANK_TOP_N=4          # Number of docs to rerank

# Confidence threshold (default: 0.0, no filtering)
MIN_RETRIEVAL_CONFIDENCE=0.0  # Filter chunks below this threshold (0-1)
```

## Features

### 1. Query-Based Retrieval

**Before**: Used fixed string `"user medical constraints and diet considerations"`  
**After**: Uses the actual user query from the request

```python
# In vault_retrieve_node
query = state["request"].query  # Actual user query
chunks, avg_confidence = retrieve_for_user(
    user_id=user_id,
    query=query,  # Pass actual query
    top_k=settings.diet_top_k,
)
```

### 2. MMR (Maximal Marginal Relevance)

MMR balances relevance and diversity by selecting documents that are:
- Relevant to the query
- Diverse from each other

**How it works**:
1. Fetch `MMR_FETCH_K` documents (default: 20)
2. Select top `top_k` documents using MMR algorithm
3. `lambda_mult` parameter controls balance:
   - `0.0` = maximum diversity (may sacrifice relevance)
   - `1.0` = maximum relevance (no diversity)
   - `0.5` = balanced (default)

**Example**:
```python
# Enable MMR
USE_MMR=true
MMR_FETCH_K=20
MMR_LAMBDA_PARAM=0.5
```

### 3. Reranking

Optional reranking using cross-encoder models for improved precision.

**Requirements**:
```bash
pip install sentence-transformers
```

**How it works**:
1. Initial retrieval (similarity search or MMR)
2. Rerank top N documents using cross-encoder
3. Return reranked results with new scores

**Model**: Uses `cross-encoder/ms-marco-MiniLM-L-12-v2` by default (good balance of speed/accuracy)

**Example**:
```python
# Enable reranking
USE_RERANKING=true
RERANK_TOP_N=4
```

### 4. Confidence Scores

Each retrieved chunk now includes:
- `confidence_score`: Similarity score (0-1, higher is better)
- `retrieval_method`: Method used (`similarity_search`, `mmr`, or `reranked`)

**In API Response**:
```json
{
  "citations": [
    {
      "type": "user_vault",
      "ref": "chunk:u123:chunk_1",
      "confidence": 0.85,
      "method": "mmr"
    }
  ]
}
```

**Average Confidence**: Stored in state as `retrieval_confidence_avg` and logged

### 5. Error Attribution

Errors are now attributed to either:
- **Retrieval errors**: Issues fetching chunks from the vault
- **Generation errors**: Issues during LLM response generation

**In State**:
```python
state["retrieval_error"] = "Error message"  # or None
state["generation_error"] = "Error message"  # or None
```

**In Logs**:
```
WARNING: Retrieval error: Vectorstore not found
WARNING: Generation error: rate_limit: ...
INFO: Retrieval confidence: 0.823
```

**In Response Handling**:
- Low confidence chunks are filtered if `MIN_RETRIEVAL_CONFIDENCE > 0`
- Retrieval errors are caught and returned to user
- Generation errors are logged and handled gracefully

## Usage Examples

### Basic Query (MMR enabled)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u123",
    "query": "What foods should I avoid with my diabetes?",
    "session_id": "sess_1"
  }'
```

**Response includes**:
- Chunks retrieved using MMR
- Confidence scores for each chunk
- Average confidence in logs

### With Reranking
```bash
# Set in .env
USE_RERANKING=true
RERANK_TOP_N=4
```

Reranking will be applied after initial retrieval.

### With Confidence Filtering
```bash
# Set in .env
MIN_RETRIEVAL_CONFIDENCE=0.7
```

Only chunks with confidence >= 0.7 will be used.

## Debug Endpoint

View retrieved chunks with confidence scores:

```bash
curl "http://localhost:8000/debug/vault/u123?query=diabetes"
```

**Response**:
```json
{
  "user_id": "u123",
  "query": "diabetes",
  "avg_confidence": 0.823,
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "text": "...",
      "confidence_score": 0.85,
      "retrieval_method": "mmr"
    }
  ],
  "total_chunks": 4
}
```

## Performance Considerations

1. **MMR**: Slightly slower than similarity search (fetches more docs)
2. **Reranking**: Adds ~100-500ms per query (depends on model)
3. **Confidence Filtering**: Minimal overhead

## Best Practices

1. **Start with MMR enabled** (`USE_MMR=true`) for better diversity
2. **Use reranking** for critical queries where precision matters
3. **Set confidence threshold** (`MIN_RETRIEVAL_CONFIDENCE`) to filter low-quality chunks
4. **Monitor logs** for retrieval confidence and errors
5. **Adjust MMR parameters** based on your use case:
   - More diversity: `MMR_LAMBDA_PARAM=0.3`
   - More relevance: `MMR_LAMBDA_PARAM=0.7`

## Troubleshooting

### Low Confidence Scores
- Check if query matches vault content
- Consider lowering `MIN_RETRIEVAL_CONFIDENCE`
- Review vault ingestion quality

### Reranking Not Working
- Ensure `sentence-transformers` is installed
- Check logs for import errors
- Reranking gracefully falls back to original order

### MMR Not Working
- Verify `USE_MMR=true` in settings
- Check that `MMR_FETCH_K >= top_k`
- Review logs for MMR selection

## Future Enhancements

Potential improvements:
- Hybrid search (keyword + semantic)
- Query expansion
- Adaptive confidence thresholds
- A/B testing framework for retrieval methods

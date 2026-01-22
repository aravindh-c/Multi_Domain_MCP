# Custom Logging Guide for Vault Operations

## Overview

The vault logger automatically logs method entry/exit, but you can also add custom log statements within your methods.

## Getting the Logger

Use `get_vault_logger()` to get the logger instance:

```python
from src.rag.logger import get_vault_logger

logger = get_vault_logger(run_type="ingest")  # or "query"
```

## Log Levels

```python
logger.debug("Detailed debug information")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error message")
```

## Examples

### In Ingest Methods (vault_store.py)

```python
@log_method_entry(run_type="ingest")
def build_index(user_id: str, text: str) -> FAISS:
    from src.rag.logger import get_vault_logger
    
    logger = get_vault_logger(run_type="ingest")
    
    # Custom log before operation
    logger.info(f"Starting index build for user_id: {user_id}")
    
    # Do work...
    chunks = splitter.split_text(text)
    
    # Custom log with data
    logger.info(f"Split text into {len(chunks)} chunks")
    
    # Warning if something unusual
    if len(chunks) > 100:
        logger.warning(f"Large number of chunks: {len(chunks)}")
    
    # Error logging (usually handled by decorator, but you can add context)
    try:
        vectorstore.save_local(path)
        logger.info(f"Index saved successfully to: {path}")
    except Exception as e:
        logger.error(f"Failed to save index: {e}")
        raise
```

### In Query Methods (retriever.py)

```python
@log_method_entry(run_type="query")
def retrieve_for_user(user_id: str, top_k: int | None = None) -> List[VaultChunk]:
    from src.rag.logger import get_vault_logger
    
    logger = get_vault_logger(run_type="query")
    
    # Log query parameters
    logger.info(f"Retrieving for user_id: {user_id}, top_k: {top_k}")
    
    # Check conditions
    if vectorstore is None:
        logger.warning("Vectorstore not found, returning empty results")
        return []
    
    # Log intermediate results
    docs = retriever.get_relevant_documents("query text")
    logger.info(f"Retrieved {len(docs)} documents")
    
    # Log filtered results
    chunks = filter_by_user(docs, user_id)
    logger.info(f"After filtering: {len(chunks)} chunks for user_id: {user_id}")
    
    return chunks
```

## Log Format

All logs (automatic + custom) appear in the same format:

```
2026-01-21 09:15:30 | INFO | vault_ingest | vault_store:build_index is entered
2026-01-21 09:15:30 | INFO | vault_ingest | Starting index build for user_id: u123
2026-01-21 09:15:31 | INFO | vault_ingest | Split text into 15 chunks
2026-01-21 09:15:35 | INFO | vault_ingest | Index saved successfully to: .faiss/user_vault.index
2026-01-21 09:15:35 | INFO | vault_ingest | vault_store:build_index is exited
```

## Best Practices

1. **Use appropriate log levels**:
   - `INFO`: Normal operation flow, important milestones
   - `WARNING`: Unusual but recoverable situations
   - `ERROR`: Errors that are caught and handled
   - `CRITICAL`: Severe errors that might crash the system

2. **Include context**:
   - Log user_id, chunk counts, file paths, etc.
   - Makes debugging easier

3. **Don't log sensitive data**:
   - Avoid logging passwords, API keys, full text content
   - The logger already filters some sensitive kwargs

4. **Use structured messages**:
   - Include key-value pairs: `f"user_id: {user_id}, chunks: {len(chunks)}"`
   - Makes logs easier to search/parse

## File Location

- Ingest logs: `log/vault_ingest_YYYYMMDD_HHMMSS.log`
- Query logs: `log/vault_query_YYYYMMDD_HHMMSS.log`

Both appear in console (RichHandler) and file.

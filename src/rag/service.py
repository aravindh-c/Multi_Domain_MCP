"""RAG HTTP service for multi-tenant chatbot. Exposes /health, /retrieve, and /ingest."""
import logging
import os

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Set FAISS path from env before importing (used by settings)
_vector_db_path = os.environ.get("VECTOR_DB_PATH", "/data/faiss")
from src.app import settings

settings.faiss_path = _vector_db_path

from src.rag.retriever import retrieve_for_user
from src.rag.vault_store import build_index as build_index_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Service", version="1.0.0")


@app.on_event("startup")
def load_secrets_from_aws():
    """Load OPENAI_API_KEY from Secrets Manager if not in env (needed for /ingest embeddings)."""
    if not os.environ.get("SECRETS_MANAGER_SECRET_NAME") or os.environ.get("OPENAI_API_KEY"):
        return
    try:
        from src.app.aws_settings import aws_settings
        key = aws_settings.get_openai_api_key()
        if key:
            os.environ["OPENAI_API_KEY"] = key
            settings.openai_api_key = key
            logger.info("Loaded OPENAI_API_KEY from Secrets Manager")
    except Exception as e:
        logger.warning("Could not load OPENAI_API_KEY from Secrets Manager: %s", e)


class RetrieveRequest(BaseModel):
    user_id: str
    query: str
    top_k: int | None = Field(None, description="Number of chunks to return")


class IngestRequest(BaseModel):
    user_id: str
    text: str = Field(..., description="Vault content to index (e.g. diet/medical notes)")


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-service"}


@app.post("/ingest")
def ingest(req: IngestRequest):
    """Ingest vault text for a user. Builds FAISS index at VECTOR_DB_PATH. Overwrites existing index for that path."""
    try:
        build_index_user(user_id=req.user_id, text=req.text)
        return {"status": "ok", "user_id": req.user_id, "message": "Index built successfully"}
    except Exception as e:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    """Retrieve vault chunks for a user/query. Returns empty list if no index."""
    try:
        chunks, avg_confidence = retrieve_for_user(
            user_id=req.user_id,
            query=req.query,
            top_k=req.top_k,
        )
        return {
            "chunks": [c.model_dump() for c in chunks],
            "avg_confidence": avg_confidence,
        }
    except Exception as e:
        logger.exception("Retrieve failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

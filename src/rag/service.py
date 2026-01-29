"""RAG HTTP service for multi-tenant chatbot. Exposes /health and /retrieve."""
import logging
import os

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Set FAISS path from env before importing retriever (used by settings)
_vector_db_path = os.environ.get("VECTOR_DB_PATH", "/data/faiss")
from src.app import settings

settings.faiss_path = _vector_db_path

from src.rag.retriever import retrieve_for_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Service", version="1.0.0")


class RetrieveRequest(BaseModel):
    user_id: str
    query: str
    top_k: int | None = Field(None, description="Number of chunks to return")


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-service"}


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

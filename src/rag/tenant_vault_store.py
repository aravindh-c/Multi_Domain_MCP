"""Tenant-aware vault store with tenant_id in metadata."""
import pathlib
from typing import List

from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.app.settings import settings
from src.rag.logger import log_method_entry


@log_method_entry(run_type="ingest")
def load_user_paragraph(tenant_id: str, user_id: str) -> str:
    """Load user vault text for a tenant/user."""
    path = pathlib.Path("data/user_vault") / f"{tenant_id}" / f"{user_id}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Vault file not found for tenant {tenant_id}, user {user_id}: {path}")
    return path.read_text(encoding="utf-8")


@log_method_entry(run_type="ingest")
def build_index(tenant_id: str, user_id: str, text: str) -> FAISS:
    """Build FAISS index with tenant_id in metadata for isolation."""
    from src.rag.logger import get_vault_logger
    
    logger = get_vault_logger(run_type="ingest")
    logger.info(f"Starting index build for tenant_id: {tenant_id}, user_id: {user_id}")
    
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=80)
    chunks = splitter.split_text(text)
    logger.info(f"Split text into {len(chunks)} chunks")
    
    # CRITICAL: Include tenant_id in metadata for namespace isolation
    documents: List[Document] = [
        Document(
            page_content=chunk,
            metadata={
                "tenant_id": tenant_id,  # Tenant isolation key
                "user_id": user_id,
                "chunk_id": f"{idx}",
                "source": "user_vault",
            }
        )
        for idx, chunk in enumerate(chunks)
    ]
    logger.info(f"Created {len(documents)} documents with tenant_id={tenant_id} in metadata")
    
    logger.info(f"Creating embeddings using model: {settings.embedding_model}")
    embeddings = OpenAIEmbeddings(model=settings.embedding_model, timeout=settings.request_timeout)
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Store per-tenant index (or use single index with tenant_id filter)
    path = pathlib.Path(settings.faiss_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Saving FAISS index to: {path.as_posix()}")
    vectorstore.save_local(path.as_posix())
    logger.info(f"Index build completed successfully for tenant_id: {tenant_id}, user_id: {user_id}")
    return vectorstore


@log_method_entry(run_type="ingest")
def ingest_tenant_user(tenant_id: str, user_id: str):
    """Ingest user vault for a tenant."""
    text = load_user_paragraph(tenant_id, user_id)
    return build_index(tenant_id, user_id, text)


if __name__ == "__main__":
    print("Building FAISS index for tenant t1, user u123...")
    ingest_tenant_user("t1", "u123")
    print(f"Done. Index stored at {settings.faiss_path}")

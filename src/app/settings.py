from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Keys must be provided via env / .env (never hardcode secrets in code)
    openai_api_key: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None
    langchain_tracing_v2: bool = True
    model_name: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    faiss_path: str = ".faiss/user_vault.index"
    mcp_price_server_url: str = "http://localhost:8001"
    mcp_finance_server_url: str = "http://localhost:8002"

    request_timeout: float = 30.0
    diet_top_k: int = 4
    response_max_tokens: int = 512
    
    # RAG improvements
    use_mmr: bool = True  # Enable MMR for diversity
    mmr_fetch_k: int = 20  # Fetch more docs for MMR, then select diverse top_k
    mmr_lambda_param: float = 0.5  # 0 = max diversity, 1 = max relevance
    use_reranking: bool = False  # Enable reranking (requires sentence-transformers)
    rerank_top_n: int = 4  # Rerank top N results
    min_retrieval_confidence: float = 0.0  # Minimum similarity score threshold (0-1)


settings = Settings()  # load once at import

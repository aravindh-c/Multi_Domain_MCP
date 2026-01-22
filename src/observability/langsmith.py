import os

from src.app.settings import settings


def configure_tracing() -> None:
    """
    Configure LangSmith/LangChain tracing via environment variables.

    We intentionally avoid importing internal tracer helpers (which change across
    langchain-core versions). If `LANGCHAIN_TRACING_V2=true` and LangSmith creds
    are present, LangChain will auto-enable tracing.
    """
    if settings.langchain_tracing_v2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    if settings.langsmith_project:
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return None

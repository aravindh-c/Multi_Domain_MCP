from fastapi import FastAPI
from pydantic import BaseModel

# Use absolute imports so the module can be run as a script from project root.
from mcp_servers.finance_server.schemas import FinanceBundle, TopGainersResult
from mcp_servers.finance_server.tools import get_finance_bundle, get_top_gainers

app = FastAPI(title="MCP Finance Server")


class BundleRequest(BaseModel):
    ticker: str
    period: str = "1mo"
    news_limit: int = 5


@app.post("/bundle", response_model=FinanceBundle)
def bundle(payload: BundleRequest):
    bundle = get_finance_bundle(payload.ticker)
    # trim news if needed
    bundle.news = bundle.news[: payload.news_limit]
    return bundle


class TopGainersRequest(BaseModel):
    limit: int = 5


@app.post("/top-gainers")
def top_gainers(payload: TopGainersRequest):
    result = get_top_gainers(limit=payload.limit)
    if result is None:
        # Return error response when feature not available
        from fastapi import HTTPException
        raise HTTPException(
            status_code=501,
            detail="Top gainers feature not yet implemented. This requires market-wide data scraping from Screener.in or an alternative data source."
        )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)

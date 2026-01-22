from fastapi import FastAPI
from pydantic import BaseModel

# Use absolute imports so the module can be run as a script from project root.
from mcp_servers.price_server.schemas import ComparisonResult
from mcp_servers.price_server.tools import compare_products

app = FastAPI(title="MCP Price Server")


class CompareRequest(BaseModel):
    query: str
    filters: dict = {}


@app.post("/compare", response_model=ComparisonResult)
def compare(payload: CompareRequest):
    return compare_products(payload.query, payload.filters)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)

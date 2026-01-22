# Multi-Domain Tool-First Chatbot

Production-shaped FastAPI + LangGraph chatbot that routes across three domains:

- Ecommerce price comparison via MCP price server
- Finance/stock info via MCP finance server (info-only)
- Diet/nutrition Q&A using a private user vault (RAG) with user_id scoping

## Quickstart

### Windows (CMD)

1. Create venv + install:
   ```
   cd D:\Users\achelladurai\Downloads\C_MCP
   python -m venv .venv
   .\.venv\Scripts\activate.bat
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. Set env vars (CMD) **for this terminal session**:
   ```
   set OPENAI_API_KEY=sk-REPLACE_WITH_YOUR_KEY
   set LANGCHAIN_TRACING_V2=true
   set LANGSMITH_API_KEY=ls-REPLACE_IF_YOU_USE_LANGSMITH
   set LANGSMITH_PROJECT=multi-domain-chatbot
   ```

   Optional (if you prefer `.env`): create `.env` manually in the repo root with:
   ```
   OPENAI_API_KEY=sk-REPLACE_WITH_YOUR_KEY
   LANGCHAIN_TRACING_V2=true
   LANGSMITH_API_KEY=ls-REPLACE_IF_YOU_USE_LANGSMITH
   LANGSMITH_PROJECT=multi-domain-chatbot
   ```

3. Build the local diet vault index (FAISS) from `data/user_vault/u123.txt`:
   ```
   python -m src.rag.vault_store
   ```

4. Start servers (**open 3 separate CMD windows**):

   - Window A (price MCP):
     ```
     cd D:\Users\achelladurai\Downloads\C_MCP
     .\.venv\Scripts\activate.bat
     python -m mcp_servers.price_server.server
     ```

   - Window B (finance MCP; live quote uses Screener HTML):
     ```
     cd D:\Users\achelladurai\Downloads\C_MCP
     .\.venv\Scripts\activate.bat
     python -m mcp_servers.finance_server.server
     ```

   - Window C (main API):
     ```
     cd D:\Users\achelladurai\Downloads\C_MCP
     .\.venv\Scripts\activate.bat
     uvicorn src.app.main:app --reload
     ```

5. Test:
   ```
   curl -X POST http://127.0.0.1:8000/chat ^
     -H "Content-Type: application/json" ^
     -d "{\"user_id\":\"u123\",\"session_id\":\"s456\",\"query\":\"Show TCS last 30 days trend and summarize latest news\",\"locale\":\"en-IN\"}"
   ```

## Endpoint

- `POST /chat` with body:
  ```json
  {"user_id":"u123","session_id":"s456","query":"Is paneer okay for dinner?","locale":"en-IN"}
  ```

Returns structured JSON including route, answer, citations, tool_calls, refusal, and meta (latency/token placeholders).

## Notes

- LangSmith tracing controlled by env vars (`LANGCHAIN_TRACING_V2=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`).
- MCP servers use mocked fixtures but enforce Pydantic schemas and deterministic outputs.
- Diet route always performs vault retrieval (FAISS, top K=4) filtered by user_id; other routes never touch vault.

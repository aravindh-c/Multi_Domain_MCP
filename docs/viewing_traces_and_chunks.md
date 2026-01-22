# Viewing LangSmith Traces & RAG Chunks

## 1. LangSmith Traces

### Setup
1. **Get LangSmith API Key**:
   - Go to https://smith.langchain.com/
   - Sign up/login
   - Go to Settings → API Keys
   - Create a new API key

2. **Set Environment Variables**:
   ```cmd
   set LANGCHAIN_TRACING_V2=true
   set LANGSMITH_API_KEY=ls-your-key-here
   set LANGSMITH_PROJECT=multi-domain-chatbot
   ```

   Or in `.env`:
   ```
   LANGCHAIN_TRACING_V2=true
   LANGSMITH_API_KEY=ls-your-key-here
   LANGSMITH_PROJECT=multi-domain-chatbot
   ```

3. **Restart your API server** after setting env vars

### Viewing Traces
1. **Go to LangSmith Dashboard**: https://smith.langchain.com/
2. **Click on "Projects"** in the sidebar
3. **Select your project** (default: `multi-domain-chatbot` or whatever you set)
4. **View runs**:
   - Each `/chat` request creates a trace
   - Click on any run to see:
     - **Intent classification** (which route was chosen)
     - **Tool calls** (MCP server calls, vault retrieval)
     - **LLM invocations** (prompts, responses, tokens)
     - **State transitions** through LangGraph nodes
     - **Latency** for each step
     - **Errors** if any occurred

### What You'll See in Traces
- **Node execution order**: intake → classify_intent → guard → (vault_retrieve | mcp_price | mcp_finance) → generate → trace
- **Intent prediction**: Route, confidence, extracted entities
- **Tool calls**: Which MCP tools were called, their inputs/outputs
- **Vault retrieval**: Query, retrieved chunks (text preview)
- **LLM calls**: System/user prompts, model responses
- **Final answer**: Generated response

### Filtering Traces
- Filter by route: `FINANCE_STOCK`, `DIET_NUTRITION`, `PRICE_COMPARE`
- Filter by user_id: Search for specific users
- Filter by date/time
- Search by query text

## 2. Viewing RAG Chunks (Vault Retrieval)

### Option A: Via Debug Endpoint (Recommended)
The API now includes a debug endpoint to see retrieved chunks:

```
GET http://127.0.0.1:8000/debug/vault/u123
```

Returns:
```json
{
  "user_id": "u123",
  "chunks": [
    {
      "chunk_id": "0",
      "text": "...",
      "source": "user_vault"
    }
  ],
  "total_chunks": 4
}
```

### Option B: Via API Response Citations
Every diet/nutrition response includes citations:

```json
{
  "citations": [
    {"type": "user_vault", "ref": "chunk:u123:health:0"},
    {"type": "user_vault", "ref": "chunk:u123:health:1"}
  ]
}
```

### Option C: Check Logs
The vault retrieval logs chunk IDs. Check your console output when making a diet query.

### Option D: Inspect FAISS Index (Advanced)
```python
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings()
vectorstore = FAISS.load_local(".faiss/user_vault.index", embeddings, allow_dangerous_deserialization=True)

# Get all documents for a user
docs = vectorstore.similarity_search("diet", k=10, filter={"user_id": "u123"})
for doc in docs:
    print(f"Chunk: {doc.metadata.get('chunk_id')}")
    print(f"Text: {doc.page_content[:100]}...")
    print("---")
```

## 3. Testing Both

1. **Make a diet query**:
   ```cmd
   curl -X POST http://127.0.0.1:8000/chat ^
     -H "Content-Type: application/json" ^
     -d "{\"user_id\":\"u123\",\"session_id\":\"s456\",\"query\":\"Is paneer okay for dinner?\",\"locale\":\"en-IN\"}"
   ```

2. **View chunks**:
   ```cmd
   curl http://127.0.0.1:8000/debug/vault/u123
   ```

3. **Check LangSmith**:
   - Go to https://smith.langchain.com/
   - Find your trace
   - Expand "vault_retrieve" node
   - See retrieved chunks in the trace

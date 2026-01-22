# Finance Tools Analysis

## Current Tools Available

### ✅ Implemented
1. **Single Stock Quote** (`finance_bundle`)
   - Current price (live from Screener.in)
   - Historical price data (fixtures)
   - News (fixtures)
   - Works for: "Show TCS price", "What's the current price of RELIANCE?"

### ⚠️ Partially Implemented
2. **Top Gainers** (`finance_top_gainers`)
   - Endpoint exists but returns 501 (not implemented)
   - Would need: Market-wide data scraping or API
   - Works for: "Top 5 gainers today", "Best performing stocks"

## Missing Tools (Common Finance Queries)

### Market-Wide Data
- **Top Gainers/Losers**: "Top 5 gainers today", "Worst performing stocks this week"
- **Sector Performance**: "How is IT sector performing?", "Best sectors today"
- **Market Indices**: "Nifty 50 status", "Sensex today"
- **Volume Leaders**: "Most traded stocks today"

### Stock Analysis
- **Company Fundamentals**: "TCS P/E ratio", "RELIANCE debt"
- **Financial Statements**: "TCS revenue last quarter", "Profit margins"
- **Ratios**: "ROE", "Debt-to-equity", "Current ratio"
- **Peer Comparison**: "Compare TCS vs Infosys"

### Market Data
- **Historical Trends**: "TCS 1 year chart", "6 month performance"
- **Volatility**: "Beta of TCS", "Volatility analysis"
- **Dividend History**: "TCS dividend yield", "Dividend dates"

### News & Events
- **Company News**: "Latest news on TCS" (partially implemented)
- **Market News**: "Market news today", "Sector updates"
- **Earnings Calendar**: "Upcoming results", "TCS earnings date"

### Calculations & Analysis
- **Portfolio Analysis**: "Calculate portfolio value"
- **Returns Calculation**: "What's my return if I bought at X?"
- **Risk Metrics**: "Sharpe ratio", "Standard deviation"

## Query Classification Strategy

### Type 1: Requires Live Market Data (Must use tools or refuse)
- "Top 5 gainers today" → Needs market-wide API
- "Current price of TCS" → Needs quote API ✅
- "Nifty 50 today" → Needs index API

### Type 2: General Finance Knowledge (Can use LLM)
- "What is P/E ratio?" → LLM can explain
- "How does stock market work?" → LLM can explain
- "What is dividend?" → LLM can explain
- "Difference between NSE and BSE?" → LLM can explain

### Type 3: Historical/Static Data (Can use tools or LLM)
- "TCS revenue 2023" → Could scrape or LLM (if trained on recent data)
- "Who owns TCS?" → Could scrape or LLM

### Type 4: Calculations (Can use LLM or tools)
- "If I bought 100 shares at ₹3000, what's my profit at ₹3500?" → LLM can calculate
- "What's 15% return on ₹1 lakh?" → LLM can calculate

## Recommendation: Hybrid Approach

1. **Tool-First for Live Data**: Use tools for real-time prices, market data, top gainers
2. **LLM Fallback for Knowledge**: Use LLM for general finance education, concepts, calculations
3. **Refusal for Unavailable Live Data**: If tool doesn't exist and query needs live data, refuse clearly

## Implementation Strategy

```python
def finance_node(state):
    query = detect_query_type(query)
    
    if query.needs_live_data:
        if tool_available:
            use_tool()
        else:
            refuse("Live data not available")
    elif query.is_general_knowledge:
        use_llm_directly()  # No tools needed
    elif query.is_calculation:
        use_llm_directly()  # LLM can do math
    else:
        try_tool_first_then_llm()
```

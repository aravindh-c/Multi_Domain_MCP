import json
import pathlib
import re
from typing import List

import httpx

from mcp_servers.finance_server.schemas import Candle, FinanceBundle, NewsItem, Quote, TopGainersResult

BASE = pathlib.Path(__file__).parent / "fixtures"


def load_json(name: str):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def _normalize_symbol(ticker: str) -> str:
    # Accept things like "TCS", "TCS.NS", "TCS.BO" and map to Screener company code.
    code = ticker.upper()
    for suffix in [".NS", ".NSE", ".BSE", ".BO"]:
        if code.endswith(suffix):
            code = code[: -len(suffix)]
            break
    return code


def fetch_live_quote_from_screener(ticker: str) -> Quote | None:
    """
    Try to get a live-ish quote for an Indian stock using Screener's company page.

    Screener is a stock analysis and screening tool for Indian equities, offering
    10+ years of financial data and tools for investors. See: https://www.screener.in/
    """
    symbol = _normalize_symbol(ticker)
    url = f"https://www.screener.in/company/{symbol}/"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MCP-Finance-Server/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return None

    # Parsing strategy based on the "Current Price" block in the ratios list:
    #   <li ...>Current Price</span> ... <span class="number">441</span>
    # We look for "Current Price" label and then the first <span class="number"> after it.
    block_match = re.search(
        r"Current Price.*?<span class=\"number\">([\d,]+(?:\.\d+)?)</span>",
        html,
        re.IGNORECASE | re.DOTALL,
    )

    price = None
    if block_match:
        price_str = block_match.group(1).replace(",", "")
        try:
            price = float(price_str)
        except ValueError:
            price = None

    if price is None:
        return None

    return Quote(
        ticker=symbol,
        price=price,
        currency="INR",
        change_pct=0.0,  # Screener HTML parsing keeps this simple for now.
        source="screener.in:html",
    )


def get_finance_bundle(ticker: str) -> FinanceBundle:
    # 1) Try live quote from Screener (Indian stocks).
    live_quote = fetch_live_quote_from_screener(ticker)

    # 2) History and news: Only use fixtures if we have ticker-specific data.
    # For now, return empty lists to avoid showing wrong ticker's data.
    # TODO: Implement ticker-specific history/news fetching.
    history: List[Candle] = []
    news: List[NewsItem] = []

    if live_quote is not None:
        # We have a live quote - use it, but skip history/news for now
        # (since we don't have ticker-specific data yet)
        quote = live_quote
    else:
        # 3) Fallback to fixture quote if Screener fetch fails or symbol unsupported.
        fixture_quote = Quote(**load_json("quote.json"))
        fixture_quote.ticker = ticker or fixture_quote.ticker
        quote = fixture_quote
        # Still no history/news when using fixture (to avoid TCS-specific data showing up)

    return FinanceBundle(quote=quote, history=history, news=news)


def get_top_gainers(limit: int = 5) -> TopGainersResult | None:
    """
    Fetch top gainers from Screener.in market data.
    
    Note: Screener doesn't have a public API for this, so this would need
    to scrape their market page or use an alternative data source.
    For now, returns None to indicate the feature is not available.
    """
    # TODO: Implement Screener market page scraping or use alternative API
    # For MVP, return None to trigger refusal
    return None

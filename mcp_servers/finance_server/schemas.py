from typing import List

from pydantic import BaseModel


class Quote(BaseModel):
    ticker: str
    price: float
    currency: str
    change_pct: float
    source: str


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    summary: str


class FinanceBundle(BaseModel):
    quote: Quote
    history: List[Candle]
    news: List[NewsItem]


class TopGainersResult(BaseModel):
    stocks: List[dict]  # List of {ticker, name, price, change_pct, volume}
    source: str
    timestamp: str

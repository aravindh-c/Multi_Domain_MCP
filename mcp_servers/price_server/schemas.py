from typing import List

from pydantic import BaseModel


class PriceItem(BaseModel):
    product_id: str
    name: str
    price: float
    currency: str
    vendor: str
    location: str
    source: str


class ComparisonResult(BaseModel):
    items: List[PriceItem]
    summary: str

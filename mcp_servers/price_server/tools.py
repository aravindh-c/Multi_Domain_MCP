import json
import pathlib
from typing import Dict, List

from mcp_servers.price_server.schemas import ComparisonResult, PriceItem

FIXTURE_PATH = pathlib.Path(__file__).parent / "fixtures" / "products.json"


def load_products() -> List[PriceItem]:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [PriceItem(**row) for row in data]


def compare_products(query: str, filters: Dict) -> ComparisonResult:
    products = load_products()
    sorted_items = sorted(products, key=lambda p: p.price)
    summary = f"Compared {len(sorted_items)} products for query '{query}'."
    return ComparisonResult(items=sorted_items, summary=summary)

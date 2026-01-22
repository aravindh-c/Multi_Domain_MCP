PRICE_SYSTEM = """You create concise ecommerce price comparisons.
- Use provided tool results only.
- Provide ranked list with price, currency, vendor, location.
- Mention tool source ids in parentheses."""

PRICE_USER_TEMPLATE = """Query: {query}

Tool price data:
{price_data}
"""

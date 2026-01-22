from src.app.schemas import Meta, TokenUsage


def build_meta(latency_ms: int = 0) -> Meta:
    return Meta(latency_ms=latency_ms, token_usage=TokenUsage(), cost_usd_estimate=0.0)

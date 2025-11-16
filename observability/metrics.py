"""Prometheus metrics."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Request metrics
scoring_requests_total = Counter(
    "scoring_requests_total",
    "Total number of scoring requests",
    ["status", "action"],
)

scoring_latency_seconds = Histogram(
    "scoring_latency_seconds",
    "Latency of scoring requests in seconds",
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0],
)

scoring_tokens_used = Histogram(
    "scoring_tokens_used",
    "Number of tokens used per request",
    buckets=[100, 200, 300, 400, 500, 750, 1000, 1500, 2000],
)

scoring_cost_usd = Counter(
    "scoring_cost_usd_total",
    "Total cost in USD",
)

# Error metrics
scoring_errors_total = Counter(
    "scoring_errors_total",
    "Total number of errors",
    ["error_type"],
)

# Security metrics
injection_attempts_total = Counter(
    "injection_attempts_total",
    "Total number of injection attempts detected",
)

# Cache metrics
cache_hit_rate = Gauge(
    "cache_hit_rate",
    "Cache hit rate (0.0 to 1.0)",
)


def get_metrics() -> tuple[str, str]:
    """Get Prometheus metrics in text format."""
    return generate_latest(), CONTENT_TYPE_LATEST

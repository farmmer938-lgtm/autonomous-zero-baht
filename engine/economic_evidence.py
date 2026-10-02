from datetime import datetime
from math import isfinite
from typing import Any
from urllib.parse import urlparse

ECONOMIC_METRICS = {
    "transaction_amount",
    "revenue",
    "provider_fee",
    "net_revenue",
    "balance_available",
    "cash_received",
}

REQUIRED_FIELDS = {
    "source_url",
    "provider",
    "retrieved_at",
    "verification_reference",
    "transaction_reference",
    "currency",
    "metrics",
}

def validate_economic_evidence(evidence: Any) -> dict:
    """Validate provider-side economic evidence without activating ingestion."""
    errors = []
    if not isinstance(evidence, dict):
        return _result(errors=["invalid_evidence"])

    for field in sorted(REQUIRED_FIELDS):
        if field not in evidence or evidence[field] in ("", None):
            errors.append(f"missing_{field}")

    source_url = str(evidence.get("source_url", "")).strip()
    if source_url:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("invalid_source_url")

    provider = str(evidence.get("provider", "")).strip()
    transaction_reference = str(evidence.get("transaction_reference", "")).strip()
    verification_reference = str(evidence.get("verification_reference", "")).strip()

    retrieved_at = evidence.get("retrieved_at")
    if retrieved_at and not _is_timezone_aware_iso(retrieved_at):
        errors.append("invalid_retrieved_at")

    currency = str(evidence.get("currency", "")).strip().upper()
    if currency and (len(currency) != 3 or not currency.isalpha()):
        errors.append("invalid_currency")

    metrics = evidence.get("metrics", {})
    if not isinstance(metrics, dict):
        errors.append("invalid_metrics")
        metrics = {}
    unknown = sorted(set(metrics) - ECONOMIC_METRICS)
    if unknown:
        errors.append("unknown_metrics:" + ",".join(unknown))

    for key, value in metrics.items():
        if key not in ECONOMIC_METRICS:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"non_numeric_metric:{key}")
        elif not isfinite(value):
            errors.append(f"non_finite_metric:{key}")
        elif value < 0:
            errors.append(f"negative_metric:{key}")

    if "transaction_amount" in metrics and "currency" not in evidence:
        errors.append("missing_currency_for_transaction")

    return _result(
        errors=errors,
        provider=provider or None,
        retrieved_at=retrieved_at,
        source_url=source_url,
        verification_reference=verification_reference or None,
        transaction_reference=transaction_reference or None,
        currency=currency or None,
        metrics=metrics,
    )

def _is_timezone_aware_iso(value: Any) -> bool:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (AttributeError, TypeError, ValueError):
        return False

def _result(**kwargs) -> dict:
    errors = kwargs.pop("errors", [])
    return {
        "verified": not errors,
        "status": "VERIFIED" if not errors else "NOT_VERIFIED",
        "errors": errors,
        **kwargs,
    }

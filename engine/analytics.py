from datetime import datetime
from urllib.parse import urlparse


ALLOWED_METRICS = {
    "impressions",
    "clicks",
    "conversions",
    "transactions",
    "revenue",
    "cash_received",
}


def validate_external_evidence(evidence: dict) -> dict:
    errors = []
    source_url = str(evidence.get("source_url", "")).strip()
    if not source_url:
        errors.append("missing_source_url")
    else:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("invalid_source_url")

    if not evidence.get("provider"):
        errors.append("missing_provider")
    if not evidence.get("retrieved_at"):
        errors.append("missing_retrieved_at")
    if not evidence.get("verification_reference"):
        errors.append("missing_verification_reference")

    metrics = evidence.get("metrics", {})
    if not isinstance(metrics, dict):
        errors.append("invalid_metrics")
        metrics = {}
    unknown = sorted(set(metrics) - ALLOWED_METRICS)
    if unknown:
        errors.append("unknown_metrics:" + ",".join(unknown))

    for key, value in metrics.items():
        if key in ALLOWED_METRICS and not isinstance(value, (int, float)):
            errors.append(f"non_numeric_metric:{key}")

    return {
        "verified": not errors,
        "status": "VERIFIED" if not errors else "NOT_VERIFIED",
        "errors": errors,
        "provider": evidence.get("provider"),
        "retrieved_at": evidence.get("retrieved_at"),
        "source_url": source_url,
        "verification_reference": evidence.get("verification_reference"),
        "metrics": metrics,
    }


def empty_economic_evidence() -> dict:
    return {
        "status": "NOT_VERIFIED",
        "metrics": {key: "not_verified" for key in sorted(ALLOWED_METRICS)},
        "reason": "No external evidence has been ingested.",
    }


def is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (TypeError, ValueError):
        return False

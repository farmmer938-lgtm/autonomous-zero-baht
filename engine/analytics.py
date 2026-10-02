from datetime import datetime
from math import isfinite
from urllib.parse import urlparse


ALLOWED_METRICS = {
    "impressions",
    "clicks",
    "conversions",
    "transactions",
    "revenue",
    "cash_received",
    "clones",
    "unique_cloners",
    "views",
    "unique_visitors",
}


def validate_external_evidence(evidence: dict) -> dict:
    errors = []
    if not isinstance(evidence, dict):
        return {
            "verified": False,
            "status": "NOT_VERIFIED",
            "errors": ["invalid_evidence"],
            "provider": None,
            "retrieved_at": None,
            "source_url": "",
            "verification_reference": None,
            "metrics": {},
        }

    source_url = str(evidence.get("source_url", "")).strip()
    if not source_url:
        errors.append("missing_source_url")
    else:
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("invalid_source_url")

    provider = str(evidence.get("provider", "")).strip()
    if not provider:
        errors.append("missing_provider")

    retrieved_at = evidence.get("retrieved_at")
    if not retrieved_at:
        errors.append("missing_retrieved_at")
    elif not is_iso_datetime(retrieved_at):
        errors.append("invalid_retrieved_at")

    verification_reference = str(
        evidence.get("verification_reference", "")
    ).strip()
    if not verification_reference:
        errors.append("missing_verification_reference")

    metrics = evidence.get("metrics", {})
    if not isinstance(metrics, dict):
        errors.append("invalid_metrics")
        metrics = {}

    if not metrics:
        errors.append("missing_metrics")

    unknown = sorted(set(metrics) - ALLOWED_METRICS)
    if unknown:
        errors.append("unknown_metrics:" + ",".join(unknown))

    for key, value in metrics.items():
        if key in ALLOWED_METRICS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"non_numeric_metric:{key}")
            elif not isfinite(value):
                errors.append(f"non_finite_metric:{key}")
            elif value < 0:
                errors.append(f"negative_metric:{key}")

    return {
        "verified": not errors,
        "status": "VERIFIED" if not errors else "NOT_VERIFIED",
        "errors": errors,
        "provider": provider or None,
        "retrieved_at": retrieved_at,
        "source_url": source_url,
        "verification_reference": verification_reference or None,
        "metrics": metrics,
    }


def empty_economic_evidence() -> dict:
    return {
        "status": "NOT_VERIFIED",
        "metrics": {
            key: "not_verified"
            for key in sorted(ALLOWED_METRICS)
        },
        "reason": "No external evidence has been ingested.",
    }


def is_iso_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (AttributeError, TypeError, ValueError):
        return False

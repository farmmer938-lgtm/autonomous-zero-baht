import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def record_measurement(research_count, drafts_count, validations, decision):
    validation_failures = sum(1 for item in validations if not item["passed"])
    passed = sum(1 for item in validations if item["passed"])
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "operational_pipeline_only",
        "research_items": research_count,
        "drafts_created": drafts_count,
        "drafts_validated": len(validations),
        "validation_passed": passed,
        "validation_failures": validation_failures,
        "publish_automatically": bool(decision.get("publish_automatically", False)),
        "external_distribution": "not_measured",
        "traffic": "not_measured",
        "clicks": "not_measured",
        "conversions": "not_measured",
        "transactions": "not_verified",
        "revenue": "not_verified",
        "cash_received": "not_verified",
    }
    out = ROOT / "data" / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_metrics.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return record

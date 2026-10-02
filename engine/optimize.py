import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except (OSError, json.JSONDecodeError):
        return default


def optimize(last_measurement=None, last_learning=None):
    """Choose the next safe operational action without enabling live publishing or economics."""
    measurement = last_measurement or _load(ROOT / "data" / "analytics" / "run_metrics.json", {})
    learning = last_learning or _load(ROOT / "data" / "analytics" / "learning.json", {})
    failures = int(measurement.get("validation_failures", 0) or 0)
    research_items = int(measurement.get("research_items", 0) or 0)
    drafts = int(measurement.get("drafts_created", 0) or 0)
    if failures:
        action = "reduce_or_hold_draft_generation_and_fix_validation"
        reason = "Validation failures were observed; scaling would be unsafe."
        expected = "Fewer validation failures on the next scheduled run."
    elif research_items == 0:
        action = "retain_bounded_research_retry_and_fallback"
        reason = "No research items were observed; preserve resilience before changing content volume."
        expected = "A future run either retrieves public-feed items or records a bounded fallback state."
    elif drafts == 0:
        action = "retain_research_and_validate_pipeline_without_publish"
        reason = "Research exists but no eligible fresh public-feed drafts were produced."
        expected = "Future runs continue collecting evidence without bypassing freshness/verification gates."
    else:
        action = "continue_current_safe_cycle"
        reason = "Operational pipeline completed without validation failures."
        expected = "The scheduled repeat continues Research → Create → Validate → Measure → Learn."

    actual = {
        "research_items": research_items,
        "drafts_created": drafts,
        "validation_failures": failures,
        "economic_status": learning.get("economic_evidence", {}).get("status", "NOT_VERIFIED"),
        "live_publish_authorized": False,
    }
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "safe_operational_optimization_only",
        "action": action,
        "reason": reason,
        "evidence": {
            "measurement": "data/analytics/run_metrics.json",
            "learning": "data/analytics/learning.json",
        },
        "expected_outcome": expected,
        "actual_outcome": actual,
        "economic_changes_allowed": False,
        "live_publish_changes_allowed": False,
    }
    out = ROOT / "data" / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "optimization.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result

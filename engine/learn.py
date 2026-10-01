import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _read_decisions(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records

def record_learning():
    decision_path = ROOT / "data" / "decisions" / "decision.log"
    records = _read_decisions(decision_path)
    recent = records[-10:]
    actions = Counter(item.get("recommended_action", "unknown") for item in recent)
    total_research = sum(int(item.get("research_items", 0)) for item in recent)
    total_drafts = sum(int(item.get("drafts_created", 0)) for item in recent)
    total_failures = sum(int(item.get("validation_failures", 0)) for item in recent)

    if not records:
        next_step = "collect_more_verified_runs_before_pattern_change"
    elif total_failures:
        next_step = "investigate_validation_failures_before_scaling"
    else:
        next_step = "continue_research_create_validate_measure_and_keep_publish_disabled"

    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": "operational_learning_only",
        "runs_considered": len(recent),
        "research_items_observed": total_research,
        "drafts_observed": total_drafts,
        "validation_failures_observed": total_failures,
        "recommended_actions_observed": dict(actions),
        "economic_evidence": {
            "external_distribution": "not_verified",
            "traffic": "not_verified",
            "conversions": "not_verified",
            "transactions": "not_verified",
            "revenue": "not_verified",
            "cash_received": "not_verified",
        },
        "next_step": next_step,
    }
    out = ROOT / "data" / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "learning.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result

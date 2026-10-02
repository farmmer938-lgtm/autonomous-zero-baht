import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from engine.economic_evidence import ingest_economic_evidence

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


def _economic_learning_state(economic_evidence=None, economic_authorized=False):
    if economic_evidence is None:
        return {
            "status": "NOT_VERIFIED",
            "ingested": False,
            "metrics": {},
            "reason": "No external economic evidence was supplied.",
        }

    result = ingest_economic_evidence(
        economic_evidence,
        authorized=economic_authorized,
    )
    if not result["ingested"]:
        return {
            "status": "NOT_VERIFIED",
            "ingested": False,
            "metrics": {},
            "reason": result["errors"][0] if result["errors"] else "economic_ingestion_disabled",
        }

    return {
        "status": "VERIFIED",
        "ingested": True,
        "metrics": result["metrics"],
        "provider": result["provider"],
        "transaction_reference": result["transaction_reference"],
        "verification_reference": result["verification_reference"],
    }


def record_learning(economic_evidence=None, economic_authorized=False):
    decision_path = ROOT / "data" / "decisions" / "decision.log"
    records = _read_decisions(decision_path)
    recent = records[-10:]
    actions = Counter(item.get("recommended_action", "unknown") for item in recent)
    total_research = sum(int(item.get("research_items", 0)) for item in recent)
    total_drafts = sum(int(item.get("drafts_created", 0)) for item in recent)
    total_failures = sum(int(item.get("validation_failures", 0)) for item in recent)
    economic = _economic_learning_state(
        economic_evidence,
        economic_authorized=economic_authorized,
    )

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
        "economic_evidence": economic,
        "next_step": next_step,
    }
    out = ROOT / "data" / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "learning.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result

import json
from datetime import datetime, timezone
from pathlib import Path
from .logger import log_event

ROOT = Path(__file__).resolve().parents[1]

def record_decision(research_count, drafts_count, validations):
    failed = sum(1 for item in validations if not item["passed"])
    if not research_count:
        action = "review_research_feeds_or_use_manual_seed_topics"
        reason = "No RSS items retrieved; no content was published."
    elif failed:
        action = "fix_validation_failures_before_any_publishing"
        reason = f"{failed} draft(s) failed validation."
    else:
        action = "human_review_drafts_then_consider_platform_compliant_publishing"
        reason = "Drafts passed basic structural checks only; factual and platform review is still required."
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "research_items": research_count,
        "drafts_created": drafts_count,
        "validation_failures": failed,
        "recommended_action": action,
        "reason": reason,
        "publish_automatically": False
    }
    folder = ROOT / "data" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "decision.log"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log_event("decision_recorded", **record)
    return record

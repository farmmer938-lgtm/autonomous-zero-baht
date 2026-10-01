import json
from pathlib import Path
from .logger import log_event
from .research import run_research
from .content import generate_drafts
from .validator import validate_drafts
from .decision import record_decision
from .measure import record_measurement
from .learn import record_learning

ROOT = Path(__file__).resolve().parents[1]

def main():
    config_path = ROOT / "config" / "system.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("no_payment_guard") is not True or config.get("budget_thb") != 0:
        raise RuntimeError("NO-PAYMENT GUARD: configuration must explicitly enforce zero spending.")
    log_event("run_started", project=config.get("project"), mode=config.get("mode"), budget_thb=0)
    try:
        opportunities = run_research(config)
    except Exception as exc:
        log_event("research_engine_failed", error=type(exc).__name__, detail=str(exc)[:250])
        raise
    drafts = generate_drafts(opportunities, int(config.get("max_drafts_per_run", 5))) if opportunities else []
    validations = validate_drafts(drafts)
    decision = record_decision(len(opportunities), len(drafts), validations)
    record_measurement(len(opportunities), len(drafts), validations, decision)
    record_learning()
    log_event("run_completed", research_count=len(opportunities), draft_count=len(drafts), next_action=decision["recommended_action"])

if __name__ == "__main__":
    main()

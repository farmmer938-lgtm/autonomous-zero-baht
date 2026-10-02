"""Safe autonomous economic-loop state machine."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any

class LoopState(str, Enum):
    RESEARCH="RESEARCH"; CREATE="CREATE"; VALIDATE="VALIDATE"; PUBLISH="PUBLISH"
    MEASURE="MEASURE"; VERIFY="VERIFY"; LEARN="LEARN"; OPTIMIZE="OPTIMIZE"
    REPEAT="REPEAT"; BLOCKED="BLOCKED"

class GateStatus(str, Enum):
    VERIFIED="VERIFIED"; PENDING="PENDING"; BLOCKED="BLOCKED"; NOT_VERIFIED="NOT_VERIFIED"

def utc_now(): return datetime.now(timezone.utc).isoformat()

def build_loop_state(*, distribution_enabled: bool, live_publish_authorized: bool,
                     economic_evidence_status: str="NOT_VERIFIED",
                     validation_failures: int=0) -> dict[str, Any]:
    if validation_failures:
        return {"state":LoopState.VALIDATE.value,"status":GateStatus.BLOCKED.value,
                "reason":"validation_failures_present","next":LoopState.VALIDATE.value,"timestamp":utc_now()}
    if not distribution_enabled or not live_publish_authorized:
        return {"state":LoopState.PUBLISH.value,"status":GateStatus.PENDING.value,
                "reason":"live_distribution_activation_required","next":LoopState.PUBLISH.value,"timestamp":utc_now()}
    if economic_evidence_status != GateStatus.VERIFIED.value:
        return {"state":LoopState.VERIFY.value,"status":GateStatus.NOT_VERIFIED.value,
                "reason":"provider_side_economic_evidence_not_verified","next":LoopState.VERIFY.value,"timestamp":utc_now()}
    return {"state":LoopState.REPEAT.value,"status":GateStatus.VERIFIED.value,
            "reason":"economic_loop_prerequisites_verified","next":LoopState.RESEARCH.value,"timestamp":utc_now()}

def validate_provider_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {"status":GateStatus.NOT_VERIFIED.value,"errors":["invalid_event"]}
    action=str(event.get("action","")).strip()
    sponsorship=event.get("sponsorship")
    if not action:
        return {"status":GateStatus.NOT_VERIFIED.value,"errors":["missing_action"]}
    if not isinstance(sponsorship,dict):
        return {"status":GateStatus.NOT_VERIFIED.value,"errors":["missing_sponsorship_object"],"action":action}
    return {"status":GateStatus.PENDING.value,"action":action,
            "transaction_reference":str(sponsorship.get("id") or sponsorship.get("node_id") or "") or None,
            "provider":"github_sponsors","verification_required":True,"errors":[]}

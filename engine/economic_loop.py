"""Safe autonomous economic-loop state machine."""
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
import json

class LoopState(str, Enum):
    RESEARCH="RESEARCH"; CREATE="CREATE"; VALIDATE="VALIDATE"; PUBLISH="PUBLISH"
    MEASURE="MEASURE"; VERIFY="VERIFY"; LEARN="LEARN"; OPTIMIZE="OPTIMIZE"
    REPEAT="REPEAT"; BLOCKED="BLOCKED"

class GateStatus(str, Enum):
    VERIFIED="VERIFIED"; PENDING="PENDING"; BLOCKED="BLOCKED"; NOT_VERIFIED="NOT_VERIFIED"

def utc_now(): return datetime.now(timezone.utc).isoformat()

def load_runtime_gates(root: Path) -> dict[str, Any]:
    """Load activation gates from versioned config without granting authorization."""
    distribution = json.loads((root / "config" / "distribution.json").read_text(encoding="utf-8"))
    economic = json.loads((root / "config" / "economic_loop.json").read_text(encoding="utf-8"))
    external_gate = distribution.get("external_platform_gate", {})
    live = economic.get("live_distribution", {})
    return {
        "distribution_enabled": distribution.get("enabled") is True,
        "live_publish_authorized": (
            external_gate.get("live_publish_authorized") is True
            and live.get("enabled") is True
            and live.get("authorized") is True
        ),
        "economic_verification_authorized": economic.get("economic_verification", {}).get("authorized") is True,
    }

def build_human_gate_checklist(gates: dict[str, Any]) -> dict[str, Any]:
    """Expose named human gates as explicit states without granting authorization."""
    distribution = bool(gates.get("distribution_enabled"))
    live_publish = bool(gates.get("live_publish_authorized"))
    economic = bool(gates.get("economic_verification_authorized"))
    checks = {
        "provider_account_setup": "NOT_VERIFIED",
        "kyc_tax_bank_2fa_if_required": "NOT_VERIFIED",
        "platform_policy_acceptance": "PENDING",
        "live_publish_authorization": "VERIFIED" if live_publish else "PENDING",
        "economic_ingestion_authorization": "VERIFIED" if economic else "PENDING",
        "distribution_runtime_enabled": "VERIFIED" if distribution else "PENDING",
    }
    return {
        "status": "READY" if all(value == "VERIFIED" for value in checks.values()) else "PENDING",
        "checks": checks,
        "verification_basis": {
            "provider_account_setup": "external_provider_authoritative_evidence_required",
            "kyc_tax_bank_2fa_if_required": "external_provider_authoritative_evidence_required",
            "platform_policy_acceptance": "human_acceptance_evidence_required",
            "live_publish_authorization": "runtime_config_gate",
            "economic_ingestion_authorization": "runtime_config_gate",
            "distribution_runtime_enabled": "runtime_config_gate",
        },
        "authorization_changes_applied": False,
    }


def build_activation_readiness(gates: dict[str, Any]) -> dict[str, Any]:
    """Report missing human/system activation gates without changing any gate."""
    checks = {
        "live_distribution_enabled": bool(gates.get("distribution_enabled")),
        "live_publish_authorized": bool(gates.get("live_publish_authorized")),
        "economic_verification_authorized": bool(gates.get("economic_verification_authorized")),
    }
    missing = [name for name, ok in checks.items() if not ok]
    return {
        "status": "READY" if not missing else "PENDING",
        "checks": checks,
        "missing_gates": missing,
        "activation_changes_applied": False,
    }


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

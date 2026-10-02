import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "distribution.json"


def load_distribution_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def build_distribution_plan(draft_paths: list[str]) -> dict[str, Any]:
    config = load_distribution_config()
    gate = config["external_platform_gate"]
    return {
        "provider": config["provider"],
        "mode": config["mode"],
        "enabled": bool(config["enabled"]),
        "publish_automatically": bool(config["publish_automatically"]),
        "gate_status": gate["status"],
        "live_publish_authorized": bool(gate["live_publish_authorized"]),
        "draft_count": len(draft_paths),
        "action": "dry_run_only",
        "publish_performed": False,
        "reason": "Distribution remains disabled until explicit human activation and external deployment verification.",
    }


def dry_run_distribution(draft_paths: list[str]) -> dict[str, Any]:
    plan = build_distribution_plan(draft_paths)
    if plan["enabled"] or plan["publish_automatically"] or plan["live_publish_authorized"]:
        raise RuntimeError("Unsafe distribution configuration: dry-run guard must remain disabled.")
    return plan


def publish(_draft_paths: list[str]) -> None:
    raise RuntimeError(
        "LIVE DISTRIBUTION BLOCKED: this adapter is intentionally disabled-by-default. "
        "Human activation and external platform verification are required."
    )

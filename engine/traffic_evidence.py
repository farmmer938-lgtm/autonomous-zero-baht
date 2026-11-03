"""Capture GitHub repository traffic as externally-attributable evidence.

GitHub's traffic API is authoritative provider-side data for this public
repository, so it satisfies the external-evidence gate without any extra
credential (the Actions GITHUB_TOKEN covers the repo it runs in). The result is
only persisted when the evidence validator marks it VERIFIED.
"""
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .logger import log_event
from .measure import capture_external_evidence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "farmmer938-lgtm/autonomous-zero-baht"


def _get(url, token):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "AutonomousZeroBahtBusinessOS/0.1",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode() or "{}")


def collect_traffic_evidence(repo=DEFAULT_REPO, token=None):
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        return {"status": "NOT_VERIFIED", "reason": "missing_github_token", "verified": False}

    base = f"https://api.github.com/repos/{repo}/traffic"
    try:
        views = _get(f"{base}/views", token)
        clones = _get(f"{base}/clones", token)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return {"status": "NOT_VERIFIED", "reason": f"traffic_fetch_failed:{type(exc).__name__}", "verified": False}

    now = datetime.now(timezone.utc).isoformat()
    evidence = {
        "provider": "github_repository_traffic",
        "retrieved_at": now,
        "source_url": f"https://github.com/{repo}/graphs/traffic",
        "verification_reference": f"github-traffic-api:{repo}:{now[:10]}",
        "metrics": {
            "views": int(views.get("count", 0)),
            "unique_visitors": int(views.get("uniques", 0)),
            "clones": int(clones.get("count", 0)),
            "unique_cloners": int(clones.get("uniques", 0)),
        },
    }

    destination = ROOT / "data" / "analytics" / "external_evidence.json"
    try:
        result = capture_external_evidence(evidence, destination)
    except ValueError as exc:
        log_event("traffic_evidence_rejected", detail=str(exc)[:200])
        return {"status": "NOT_VERIFIED", "reason": "evidence_rejected", "verified": False}

    log_event("traffic_evidence_captured", metrics=evidence["metrics"],
              source_url=evidence["source_url"], status=result["status"])
    return result


if __name__ == "__main__":
    print(json.dumps(collect_traffic_evidence(), ensure_ascii=False))

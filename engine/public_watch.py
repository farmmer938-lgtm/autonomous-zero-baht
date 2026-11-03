"""Public-surface watchdog (GitHub Actions, free, no secrets).

Runs on GitHub's infrastructure instead of a quota-limited OpenHands sandbox, so it can
check AF's public revenue surfaces every few minutes at zero cost and zero token use.
Everything it reads is public: no credentials, so nothing sensitive can leak.

It writes data/public_watch.json and exits non-zero if a critical surface is down, which
makes GitHub email the owner automatically.

Entrypoint: python -m engine.public_watch
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public_watch.json"

SURFACES = {
    "storefront": ("https://app.do.ink/stores/navintas", True),
    "catalog": ("https://farmmer938-lgtm.github.io/aeris-store/af-studio-m938-2/", True),
    "research_site": ("https://farmmer938-lgtm.github.io/autonomous-zero-baht/", True),
    "opentask": ("https://opentask.ai/api/tasks", False),
}

UA = {"User-Agent": "af-public-watch/1.0"}


def fetch(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def funded_titles(body: str):
    try:
        data = json.loads(body)
    except Exception:
        return []
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    out = []
    for t in tasks:
        b = t.get("budgetText") or ""
        if b and b not in ("0 USDC", "Unpaid pilot — public credit only",
                           "Free - community contribution") and "internal" not in b:
            out.append(t.get("title"))
    return sorted(x for x in out if x)


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    surfaces, down = {}, []
    for name, (url, critical) in SURFACES.items():
        code, body = fetch(url)
        entry = {"url": url, "http": code, "ok": code == 200}
        if name == "opentask":
            titles = funded_titles(body)
            entry["funded_tasks"] = len(titles)
            entry["funded_titles"] = titles
        surfaces[name] = entry
        if critical and code != 200:
            down.append(name)

    report = {"schema": "af.public_watch.v1", "checked_at": now,
              "healthy": not down, "down": down, "surfaces": surfaces}

    prev = None
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = None
    changed = not prev or prev.get("down") != down or [
        s.get("ok") for s in (prev or {}).get("surfaces", {}).values()
    ] != [s.get("ok") for s in surfaces.values()]
    if prev and prev.get("surfaces", {}).get("opentask", {}).get("funded_titles") != \
            surfaces["opentask"].get("funded_titles"):
        changed = True
    report["changed"] = bool(changed)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"healthy": report["healthy"], "down": down,
                      "opentask_funded": surfaces["opentask"].get("funded_tasks")},
                     ensure_ascii=False))
    if down:
        print(f"ALERT: surfaces down -> {down}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

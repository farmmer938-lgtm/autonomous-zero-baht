#!/usr/bin/env python3
"""HOLD window recorder for E2 (2026-11-25 -> 2026-12-25).

K's instruction: keep the ten pages, check them periodically, record the timestamp and the
result, count no bot/HTTP-200/sitemap as a visitor, and decide on 2026-12-25 from evidence.

This tool only records. It reuses af_publish_check for the HTTP side so the two can never
disagree, and it refuses to write a "visitor" number, because nothing here can measure one.

  python3 tools/af_e2_hold.py --record     # append one timestamped check to data/e2_hold_log.jsonl
  python3 tools/af_e2_hold.py --status     # print the hold window and the latest check
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_publish_check as pc  # noqa: E402

LOG = Path("data/e2_hold_log.jsonl")
PANEL_DIR = Path("site/audit/e2")
HOLD_START = date(2026, 11, 25)
DECISION_DATE = date(2026, 12, 25)
PANEL_PAGES = 10


# A public repo is not a place for a customer's identity. These shapes never enter the log.
PII_PATTERNS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"), "email address"),
    (re.compile(r"(?<!\d)(?:0|\+66)[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)"), "phone number"),
    (re.compile(r"\b(?:promptpay|พร้อมเพย์)\b", re.I), "payment handle"),
    (re.compile(r"\b0x[0-9a-fA-F]{64}\b"), "private key"),
    (re.compile(r"\b(?:seed phrase|mnemonic|private key)\b", re.I), "key material"),
)


def assert_no_pii(row):
    """Raise if a record would publish a way to identify or charge a person."""
    blob = json.dumps(row, ensure_ascii=False)
    for pattern, what in PII_PATTERNS:
        if pattern.search(blob):
            raise ValueError(f"refusing to write a {what} into the public hold log")
    return row


def panel_pages():
    """The E2 panel itself: token pages plus the index, checked one by one."""
    return sorted(p.name for p in PANEL_DIR.glob("*.html")) if PANEL_DIR.exists() else []


def record(now=None, checker=None):
    """One measurement. Unmeasurable things stay null; they are never estimated."""
    now = now or datetime.now(timezone.utc)
    checker = checker or pc
    rows = [{"path": p, "status": checker.head(pc.BASE + p)} for p in pc.PATHS]
    live = [r["path"] for r in rows if r["status"] == 200]
    panel = [{"page": name, "status": checker.head(pc.BASE + "audit/e2/" + name)}
             for name in panel_pages()]
    panel_live = [r["page"] for r in panel if r["status"] == 200]
    return {
        "schema": "af.e2.hold_check.v1",
        "at": now.isoformat(),
        "day_of_hold": (now.date() - HOLD_START).days,
        "decision_date": DECISION_DATE.isoformat(),
        "paths_checked": len(rows),
        "paths_200": live,
        "pages_200": len(live),
        # Three different numbers, kept apart so a report can never add them up by accident.
        "counts": {
            "e2_paths_checked": sum(1 for r in rows if r["path"].startswith("audit/e2/")),
            "html_pages_live": len([p for p in live if not p.endswith((".xml", ".txt"))]),
            "panel_pages_live": len(panel_live),
            "panel_pages_expected": PANEL_PAGES + 1,
        },
        "panel": {"live": panel_live, "dead": [r["page"] for r in panel if r["status"] != 200]},
        "measurement": {"scheduled_runner": None,
                        "mode": "on-demand: no workflow invokes this tool" if not scheduled()
                        else "scheduled"},
        # A 200 is the site answering, not a reader. Both stay null until something measures them.
        "visits": None,
        "discovery": {"search_console": None, "referrals": None},
        "enquiries": {"genuine": 0, "bot": None, "owner": None, "self_test": None},
        "orders": 0,
        "paid_usdc": 0.0,
        "cost_usdc": 0.0,
        "net_usdc": 0.0,
        "note": ("HTTP 200, sitemap and deploy success are recorded as availability only and are "
                 "not counted as visitors. discovery stays null until something measures it: "
                 "null means 'not measured', 0 would mean 'measured, nothing found'."),
    }


def scheduled():
    """True only if some workflow actually invokes this tool. It does not, so it returns False."""
    wf = Path(".github/workflows")
    if not wf.exists():
        return False
    return any("af_e2_hold" in f.read_text(encoding="utf-8", errors="ignore")
               for f in wf.glob("*.yml"))


def automated_availability_checks(rel="data/published.json"):
    """Commits by the 6-hourly pipeline that touched published.json — an availability trail."""
    try:
        out = subprocess.run(["git", "log", "--format=%aI", "--", rel],
                             capture_output=True, text=True, timeout=20).stdout.split()
        return {"source": rel, "commits": len(out), "first": out[-1] if out else None,
                "last": out[0] if out else None}
    except Exception:
        return {"source": rel, "commits": None, "first": None, "last": None}


def verify_log(path=LOG):
    """The log may only grow, must stay PII-free, and its timestamps must not go backwards."""
    problems, rows = [], []
    if not path.exists():
        return {"ok": True, "records": 0, "problems": problems}
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            problems.append(f"line {i}: not JSON")
            continue
        try:
            assert_no_pii(row)
        except ValueError as e:
            problems.append(f"line {i}: {e}")
        rows.append(row)
    stamps = [r.get("at") for r in rows]
    if stamps != sorted(stamps):
        problems.append("timestamps are not monotonic (a record was edited or reordered)")
    return {"ok": not problems, "records": len(rows), "problems": problems,
            "first": stamps[0] if stamps else None, "last": stamps[-1] if stamps else None}


def append(row, path=LOG):
    assert_no_pii(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def status(path=LOG, today=None):
    today = today or date.today()
    rows = []
    if path.exists():
        rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {"hold_start": HOLD_START.isoformat(),
            "decision_date": DECISION_DATE.isoformat(),
            "days_left": (DECISION_DATE - today).days,
            "checks": len(rows),
            "measurement_mode": "scheduled" if scheduled() else "on-demand (no workflow runs it)",
            "automated_availability_trail": automated_availability_checks(),
            "log_integrity": verify_log(path),
            "latest": rows[-1] if rows else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--verify-log", action="store_true")
    a = ap.parse_args()
    if a.record:
        row = append(record())
        print(json.dumps({k: row[k] for k in ("at", "day_of_hold", "pages_200")}))
        return 0
    if a.verify_log:
        print(json.dumps(verify_log(), ensure_ascii=False, indent=1))
        return 0
    print(json.dumps(status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

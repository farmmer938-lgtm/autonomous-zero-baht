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
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_publish_check as pc  # noqa: E402

LOG = Path("data/e2_hold_log.jsonl")
HOLD_START = date(2026, 11, 25)
DECISION_DATE = date(2026, 12, 25)
PANEL_PAGES = 10


def record(now=None, checker=None):
    """One measurement. Unmeasurable things stay null; they are never estimated."""
    now = now or datetime.now(timezone.utc)
    checker = checker or pc
    rows = [{"path": p, "status": checker.head(pc.BASE + p)} for p in pc.PATHS]
    live = [r["path"] for r in rows if r["status"] == 200]
    return {
        "schema": "af.e2.hold_check.v1",
        "at": now.isoformat(),
        "day_of_hold": (now.date() - HOLD_START).days,
        "decision_date": DECISION_DATE.isoformat(),
        "paths_checked": len(rows),
        "paths_200": live,
        "pages_200": len(live),
        "panel_pages": PANEL_PAGES,
        # A 200 is the site answering, not a reader. Both stay null until something measures them.
        "visits": None,
        "discovery": {"search_console": None, "referrals": None},
        "enquiries": {"genuine": 0, "bot": None, "owner": None, "self_test": None},
        "orders": 0,
        "paid_usdc": 0.0,
        "cost_usdc": 0.0,
        "net_usdc": 0.0,
        "note": ("HTTP 200, sitemap and deploy success are recorded as availability only and are "
                 "not counted as visitors."),
    }


def append(row, path=LOG):
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
            "latest": rows[-1] if rows else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.record:
        row = append(record())
        print(json.dumps({k: row[k] for k in ("at", "day_of_hold", "pages_200")}))
        return 0
    print(json.dumps(status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

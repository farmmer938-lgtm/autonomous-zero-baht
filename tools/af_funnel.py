#!/usr/bin/env python3
"""The funnel, with each stage measured differently on purpose.

  visitors  unknown. There is no analytics account, and inventing page views would be the
            first lie in the report. Recorded as null with the reason.
  interest  a stranger opened an `audit-request` issue: a fact the GitHub API can count.
  delivered a report was produced for that issue (site/api/orders/*.json).
  paid      a confirmed, third-party, >=12-confirmation payment in the ledger.

Nothing is inferred upward: interest does not become a customer, and delivery does not
become revenue.

Usage:
  python3 tools/af_funnel.py                       # read local order files only
  python3 tools/af_funnel.py --issues-json i.json  # plus issues from `gh issue list --json`
  python3 tools/af_funnel.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ORDERS = Path("site/api/orders")
PAID = "site/paid/index.json"
OUT = "data/funnel.json"


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def orders():
    if not ORDERS.exists():
        return []
    return [load(p, {}) for p in sorted(ORDERS.glob("*.json"))]


def compute(issue_rows, order_rows, paid):
    """Pure. issue_rows: [{"number","labels":[{"name"}],"createdAt"}]."""
    requested = [i for i in issue_rows
                 if "audit-request" in {l["name"] for l in (i.get("labels") or [])}]
    delivered = [o for o in order_rows if o.get("status") == "delivered_unpaid"]
    failed = [o for o in order_rows if o.get("status") == "failed"]
    cash_rows = [p for p in (paid.get("payments") or [])
                 if p.get("confirmed") and p.get("orderKey") and p.get("txHash")]
    cash = round(sum(float(p.get("amount_usdc") or 0) for p in cash_rows), 6)
    return {
        "visitors": None,
        "visitors_note": "no analytics account; page views are unknown, not zero",
        "interest": len(requested),
        "interest_note": "distinct audit-request issues opened by strangers",
        "delivered": len(delivered),
        "failed": len(failed),
        "paid_orders": len(cash_rows),
        "cash_usdc": cash,
        "conversion": {
            "interest_to_delivered": (round(len(delivered) / len(requested), 3)
                                      if requested else None),
            "delivered_to_paid": (round(len(cash_rows) / len(delivered), 3)
                                  if delivered else None),
        },
        "issues": [{"number": i.get("number"), "createdAt": i.get("createdAt")}
                   for i in requested],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues-json")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    issue_rows = load(a.issues_json, []) if a.issues_json else []
    out = {
        "schema": "af.funnel.v1",
        "at": datetime.now(timezone.utc).isoformat(),
        **compute(issue_rows, orders(), load(PAID, {})),
    }
    print(json.dumps({k: out[k] for k in ("visitors", "interest", "delivered", "failed",
                                          "paid_orders", "cash_usdc", "conversion")},
                     indent=1))
    if a.write:
        Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

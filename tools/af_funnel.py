#!/usr/bin/env python3
"""The funnel, with eight stages that are never inferred from each other.

  published          a page AF owns answers 200                     (data/published.json)
  reach              human readers                                  ALWAYS null here
  engagement         a stranger replied to something AF published    (issue comments)
  qualified_interest an `audit-request` issue with a chain + address
  orders             an order record exists for that issue
  delivered          the report was produced (status delivered_unpaid)
  paid               confirmed, third-party, >=12-confirmation ledger row
  net_revenue        paid cash minus service costs

Two rules keep this honest, and both are enforced by tests:

1. **Reach stays null.** There is no analytics account. A relay accepting a post, a sitemap
   crawl and an HTTP 200 are all evidence of publication, not of a reader, so none of them
   is allowed to increment reach.
2. **Nothing rolls upward.** A delivery is not a sale; an order is not a payment; a page is
   not an audience.

Duplicate events are collapsed (one order per issue, one payment per txHash) and AF's own
`self-test` issues are removed from every stage.

Usage:
  python3 tools/af_funnel.py --write
  python3 tools/af_funnel.py --issues-json /tmp/issues.json --write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ORDERS = Path("site/api/orders")
PAID = "site/paid/index.json"
PUBLISHED = "data/published.json"
OUT = "data/funnel.json"
STAGES = ("published", "reach", "engagement", "qualified_interest", "orders",
          "delivered", "paid", "net_revenue")


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def orders():
    """Latest record per issue: a re-run must not add a second order."""
    by_issue = {}
    if ORDERS.exists():
        for p in sorted(ORDERS.glob("*.json")):
            o = load(p, {})
            if isinstance(o.get("issue"), int):
                by_issue[o["issue"]] = o
    return list(by_issue.values())


def payments(paid):
    """One row per txHash, confirmed only, with an order key. Anything else is not cash."""
    seen, rows = set(), []
    for p in (paid.get("payments") or []):
        tx = p.get("txHash")
        if not (p.get("confirmed") and p.get("orderKey") and tx) or tx in seen:
            continue
        seen.add(tx)
        rows.append(p)
    return rows


def compute(issue_rows, order_rows, paid, published):
    """Pure. Every stage is counted from its own evidence."""
    def labels(i):
        return {l["name"] for l in (i.get("labels") or [])}

    own = {i.get("number") for i in issue_rows if "self-test" in labels(i)}
    asked = [i for i in issue_rows
             if "audit-request" in labels(i) and i.get("number") not in own]
    asked_numbers = {i.get("number") for i in asked}

    # Orders that belong to nobody who asked are still orders — they came from the form.
    kept = [o for o in order_rows
            if o.get("issue") not in own and not o.get("self_test")]
    delivered = [o for o in kept if o.get("status") == "delivered_unpaid"]
    cash_rows = payments(paid)
    cash = round(sum(float(p.get("amount_usdc") or 0) for p in cash_rows), 6)
    costs = 0.0  # every service AF uses is on a free tier; a paid one must be added here

    engaged = 0
    for i in asked:
        for c in (i.get("comments") or []):
            author = ((c.get("author") or {}).get("login") or "").lower()
            if author and author not in ("github-actions", "github-actions[bot]"):
                engaged += 1
                break

    return {
        "published": (published or {}).get("published"),
        "published_note": (published or {}).get("note"),
        "reach": None,
        "reach_note": ("no analytics account. 200 responses, sitemap crawls and relay "
                       "acceptances are publication evidence, not readers"),
        "engagement": engaged or None,
        "engagement_note": ("strangers who replied on an AF issue; null when there is no "
                            "reply data, never 0 by assumption"),
        "qualified_interest": len(asked),
        "orders": len(kept),
        "delivered": len(delivered),
        "paid": len(cash_rows),
        "net_revenue": round(cash - costs, 6),
        "cash_usdc": cash,
        "costs_usd": costs,
        "conversion": {
            "published_to_interest": (round(len(asked) / published["published"], 3)
                                      if (published or {}).get("published") else None),
            "interest_to_delivered": (round(len(delivered) / len(asked), 3)
                                      if asked else None),
            "delivered_to_paid": (round(len(cash_rows) / len(delivered), 3)
                                  if delivered else None),
        },
        "excluded_self_tests": sorted(n for n in own if n is not None),
        "unasked_orders": sorted(o.get("issue") for o in kept
                                 if o.get("issue") not in asked_numbers),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issues-json")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    issue_rows = load(a.issues_json, []) if a.issues_json else []
    stage = compute(issue_rows, orders(), load(PAID, {}), load(PUBLISHED, {}))
    out = {"schema": "af.funnel.v2",
           "at": datetime.now(timezone.utc).isoformat(), **stage}
    print(json.dumps({k: out[k] for k in STAGES}, indent=1))
    if a.write:
        Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

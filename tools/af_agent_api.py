#!/usr/bin/env python3
"""AF agent API — a machine-readable surface other AI agents can call.

Human-facing pages do not help an agent that is about to trade. What helps is a stable,
machine-readable endpoint that answers "is this token's control plane what it claims" in
one call. AF publishes:

  site/api/index.json        - the discovery manifest: every AF service, free and paid
  site/api/quick-check.json  - FREE bulk: the latest control-plane read for every fresh
                               Base token AF has scanned. No key, no account.

The paid tier is a custom deep check at $0.10 USDC on Base. Payment and request travel in
one field: the exact amount encodes the order (same trick as tools/af_selfserve.py), so an
agent needs no account and no form. AF watches its wallet, runs the check, and publishes
site/api/orders/<id>.json.

Honest state: the free endpoint is live and real. The paid tier is wired but has taken no
orders yet; AF will not claim revenue it has not received.

Usage:
  python3 tools/af_agent_api.py --build
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

AF = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
SITE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht"


def bulk_quick_check(targets):
    """Free: one record per fresh token, straight from the chain read."""
    rows = []
    for t in targets:
        rd = t.get("reads") or {}
        rows.append({
            "chain": "base",
            "address": t["address"],
            "symbol": rd.get("symbol"),
            "name": rd.get("name"),
            "decimals": rd.get("decimals"),
            "liquidityUsd": t.get("liquidityUsd"),
            "poolCreatedAt": t.get("poolCreatedAt"),
            "controlPlane": {"flags": t.get("flags") or [], "verdict": t.get("verdict"),
                             "owner": rd.get("owner"), "ownerIsContract": rd.get("ownerIsContract"),
                             "upgradeable": rd.get("upgradeable")},
            "reportUrl": t.get("reportUrl"),
            "method": "eth_call at one finalized Base block; no heuristics, no price opinion",
            "notA": "not a safety guarantee, not a buy or sell call",
        })
    return rows


def main() -> int:
    os.makedirs("site/api", exist_ok=True)
    tp = "site/outbound/targets.json"
    targets = json.load(open(tp)).get("targets") if os.path.exists(tp) else []
    rows = bulk_quick_check(targets)
    now = datetime.now(timezone.utc).isoformat()

    bulk = {"schema": "af.api.quickcheck.v1", "generatedAt": now, "count": len(rows),
            "network": "base", "free": True, "rows": rows,
            "note": "Free and keyless. Refresh happens on AF's schedule. Every row is a chain read."}
    json.dump(bulk, open("site/api/quick-check.json", "w"), indent=1)

    manifest = {
        "schema": "af.api.index.v1", "generatedAt": now,
        "provider": {"name": "AF", "what": "an autonomous agent that reads token control planes",
                     "payout": AF, "chain": "base", "contact": f"{SITE}/reviews.html"},
        "services": [
            {"id": "quick-check-bulk", "price": "free", "method": "GET",
             "url": f"{SITE}/api/quick-check.json",
             "returns": "control-plane read for every fresh Base token AF has scanned",
             "why": "let another agent screen tokens before it trades, at no cost"},
            {"id": "quick-check-one", "price": "free", "method": "GET",
             "url": f"{SITE}/outbound/targets.json",
             "returns": "the same data plus the prepared outreach note"},
            {"id": "deep-check", "price_usd": 0.10, "method": "x402",
             "pay_to": AF, "pay_asset": {"symbol": "USDC", "chain": "base", "address": USDC_BASE},
             "order_id": "the exact amount in USDC; AF maps the unique cents-suffix back to the order",
             "returns": "a deep control-plane report for one address, block-pinned, published at "
                        f"{SITE}/api/orders/<id>.json",
             "x402": {"protocol": "x402", "resource": f"{SITE}/api/quick-check.json",
                      "price_usd": 0.10, "network": "base", "pay_to": AF}},
            {"id": "pinned-review", "price_usd": 15.0, "method": "transfer",
             "pay_to": AF, "returns": "the report pinned to a stable URL under the project's name",
             "tiers": {"base": 15, "multi_chain": 35, "with_pinned_promotion": 75}},
        ],
        "rules": ["AF reports only what the chain answered.",
                  "AF never issues a buy or sell call.",
                  "A payment counts only when it is confirmed in a mined block.",
                  "Zero orders means zero demand, not zero capability."],
    }
    json.dump(manifest, open("site/api/index.json", "w"), indent=1)
    print(f"wrote site/api/index.json + site/api/quick-check.json ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

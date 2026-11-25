#!/usr/bin/env python3
"""One page that answers the only question that matters: did money actually arrive?

Six numbers, each with the file it came from, so a reader can check any of them:

  found      paid work the ranker can see (data/opportunities.json)
  taken      opportunities AF could act on today, net of cost
  cash       USDC a third party paid for an order (site/paid/index.json, strict ledger)
  pending    matched but not yet 12 blocks deep
  costs      money AF spent on services (must stay 0)
  needs_you  claims blocked on an identity only K can provide

The chain audit is quoted as a separate, wider truth: it counts every inbound transfer,
including the ones no order explains, so the report never claims more than the ledger.

Read-only. Writes data/revenue_report.json and data/REVENUE_REPORT.md.

Usage:
  python3 tools/af_revenue_report.py
  python3 tools/af_revenue_report.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OPP = "data/opportunities.json"
PAID = "site/paid/index.json"
LEDGER = "data/paid_ledger.json"
CHAIN = "data/revenue_verify.json"
WATCH = "data/public_watch.json"
MANIFEST = "site/data/live_endpoint.json"
OUT_JSON = "data/revenue_report.json"
OUT_MD = "data/REVENUE_REPORT.md"
MANIFEST_MAX_AGE_H = 3.0
# Every service AF uses is free. If a line is ever added here, the report shows a real cost.
SERVICE_COSTS_USD: list[dict] = []


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def age_hours(stamp, now=None):
    """Hours since an ISO timestamp, or None when it cannot be parsed."""
    try:
        t = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except Exception:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return round((now - t).total_seconds() / 3600, 2)


def cash_from_paid_index(paid):
    """Strict: only rows that are confirmed, carry an order key, and name a tx."""
    rows = [p for p in (paid.get("payments") or [])
            if p.get("confirmed") and p.get("orderKey") and p.get("txHash")]
    return round(sum(float(p.get("amount_usdc") or 0) for p in rows), 6), len(rows)


def pending_from_ledger(ledger):
    """Matched but not final: kept apart so nobody reads a tip-block transfer as a sale."""
    return [p for p in (ledger.get("payments") or []) if not p.get("confirmed")]


def monitor(now=None):
    """H5: the surfaces that silently break — manifest age, watch health, failed runs."""
    manifest = load(MANIFEST)
    watch = load(WATCH)
    health = load("data/workflow_health.json")
    age = age_hours(manifest.get("updated_at"), now)
    runs = health.get("runs") or []
    failed_runs = [r for r in runs if r.get("failed")]
    return {
        "manifest_age_hours": age,
        "manifest_stale": (age is None) or (age > MANIFEST_MAX_AGE_H),
        "manifest_base": manifest.get("public_base"),
        "public_watch_healthy": bool(watch.get("healthy")),
        "public_watch_fail": watch.get("fail") or [],
        "public_watch_warn": watch.get("warn") or [],
        "workflow_runs_seen": len(runs),
        "workflow_runs_failed": len(failed_runs),
        "last_workflow_failures": [{"workflow": r.get("workflow"), "at": r.get("at"),
                                    "failed": r.get("failed")} for r in failed_runs[-3:]],
    }


def build_report(now=None):
    now = now or datetime.now(timezone.utc)
    opp = load(OPP)
    paid = load(PAID)
    ledger = load(LEDGER)
    chain = load(CHAIN)
    items = opp.get("opportunities") or []
    by_verdict = {}
    for i in items:
        by_verdict.setdefault(i.get("verdict"), []).append(i)
    cash, cash_rows = cash_from_paid_index(paid)
    costs = round(sum(float(c.get("usd") or 0) for c in SERVICE_COSTS_USD), 6)
    needs_owner = by_verdict.get("needs_owner", [])
    return {
        "schema": "af.revenue_report.v1",
        "at": now.isoformat(),
        "headline": {
            "cash_received_usdc": cash,
            "cash_payments": cash_rows,
            "net_after_costs_usdc": round(cash - costs, 6),
            "act_now_opportunities": len(by_verdict.get("act_now", [])),
            "needs_owner": len(needs_owner),
        },
        "found": {
            "source": OPP,
            "checked_at": opp.get("checked_at"),
            "total": len(items),
            "by_verdict": {k: len(v) for k, v in by_verdict.items()},
            "act_now": [{k: i.get(k) for k in ("id", "rail", "title", "net_usd", "url")}
                        for i in by_verdict.get("act_now", [])],
            "rails_not_counted": opp.get("rails_not_counted") or [],
        },
        "taken": {"note": "no claim has been executed; the ledger has no third-party order"},
        "cash": {
            "source": PAID,
            "usdc": cash,
            "payments": cash_rows,
            "ledger_rows": len(ledger.get("payments") or []),
        },
        "pending": {
            "count": len(pending_from_ledger(ledger)),
            "note": "matched but fewer than 12 confirmations; not counted as cash",
        },
        "costs": {"usd": costs, "lines": SERVICE_COSTS_USD,
                  "note": "free tiers only; a paid service would appear here as a negative"},
        "needs_you": [{"id": i.get("id"), "title": i.get("title"), "reasons": i.get("reasons")}
                      for i in needs_owner],
        "chain_audit": {
            "source": CHAIN,
            "at": chain.get("at"),
            "verdict": chain.get("verdict"),
            "inbound_usdc_total": chain.get("inbound_usdc_total"),
            "inbound_tx_total": chain.get("inbound_tx_total"),
            "balance_usdc": chain.get("balance_usdc"),
            "note": "window is the last 49k blocks; tools/af_inbound_audit.py walks all of it",
        },
        "monitor": monitor(now),
    }


def render_md(r):
    h, m = r["headline"], r["monitor"]
    lines = [
        "# AF revenue report",
        "",
        f"generated {r['at']}",
        "",
        "| number | value |",
        "|---|---|",
        f"| cash received (third-party orders) | **{h['cash_received_usdc']} USDC** |",
        f"| payments counted | {h['cash_payments']} |",
        f"| service costs | {r['costs']['usd']} USD |",
        f"| net | {h['net_after_costs_usdc']} USDC |",
        f"| opportunities AF can take today | **{h['act_now_opportunities']}** |",
        f"| claims waiting on the owner | {h['needs_owner']} |",
        "",
        "## Found",
        "",
        f"{r['found']['total']} listings, checked {r['found']['checked_at']} — "
        + ", ".join(f"{k}: {v}" for k, v in sorted(r["found"]["by_verdict"].items())),
        "",
    ]
    for i in r["found"]["act_now"]:
        lines.append(f"- **{i['id']}** {i['title']} — net {i['net_usd']} — {i['url']}")
    if not r["found"]["act_now"]:
        lines.append("- nothing payable today")
    lines += ["", "## Pending", "", f"{r['pending']['count']} transfer(s) awaiting confirmations.", ""]
    lines += ["## Needs you", ""]
    lines += [f"- {i['id']}: {i['title']}" for i in r["needs_you"]] or ["- nothing"]
    lines += [
        "",
        "## Monitor",
        "",
        f"- paid host manifest: {m['manifest_age_hours']}h old"
        f"{' — **STALE**' if m['manifest_stale'] else ''} ({m['manifest_base']})",
        f"- public watch healthy: {m['public_watch_healthy']} "
        f"(fail {len(m['public_watch_fail'])}, warn {len(m['public_watch_warn'])})",
        f"- workflow runs seen: {m['workflow_runs_seen']}, failed: {m['workflow_runs_failed']}",
        "",
        "## Chain audit (wider than the ledger)",
        "",
        f"{r['chain_audit']['inbound_usdc_total']} USDC inbound over "
        f"{r['chain_audit']['inbound_tx_total']} transfers in the last 49k blocks, "
        f"verdict {r['chain_audit']['verdict']}, balance {r['chain_audit']['balance_usdc']}.",
        "Most of that is AF's own capital returning from swaps; "
        "`tools/af_inbound_audit.py` shows the split.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    report = build_report()
    md = render_md(report)
    print(md)
    if a.write:
        Path(OUT_JSON).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                                  encoding="utf-8")
        Path(OUT_MD).write_text(md, encoding="utf-8")
        print("wrote", OUT_JSON, "and", OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())

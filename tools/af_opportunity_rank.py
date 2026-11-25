#!/usr/bin/env python3
"""Rank paid work by what it would actually pay, not by the number printed on the board.

Every public rail states a reward. Almost none of them state whether the money exists, what
it costs to start, or how often anyone gets paid. This turns those three questions into a
verdict per opportunity, so AF stops spending days on listings that cannot pay.

Verdicts, in the order they are applied:
  loss         net <= 0 once the cost to start is subtracted (the $10 Frantic rebate is
               this: you must fund $10 of someone else's work to earn $10 back)
  needs_owner  the money is real but the claim needs an identity only K can provide
  act_now      funded, claimable, net > 0, no identity gate
  watch        funded but nothing AF can claim right now (no slot, window closed)
  ignore       the reward is credits or an advertisement, not money the rail holds

Read-only: public HTTP APIs, no keys, no transactions.

Usage:
  python3 tools/af_opportunity_rank.py            # print the ranking
  python3 tools/af_opportunity_rank.py --write    # also write data/opportunities.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = {"User-Agent": "af-opportunity-rank/1.0"}
FRANTIC_BOARD = "https://gofrantic.com/v1/board"
FRANTIC_DETAIL = "https://gofrantic.com{path}"  # the board item's own api_url
NONSYNTHETIC = "https://api.nonsynthetic.net/api/v1/board/tasks?status=open"
OUT = "data/opportunities.json"

# Rails AF already holds credentials for or has measured. Listed so the report says what is
# NOT being counted instead of silently omitting it. `checked` is False when the number in
# the file is a note from a past run rather than a live read.
RAILS = [
    {"rail": "x402 cashier", "status": "PARKED", "checked": True,
     "why": "no server in this repo, ephemeral host is dead (404), free hosting needs a new account"},
    {"rail": "memo-invoice", "status": "LIVE, no buyers", "checked": True,
     "why": "af_selfserve invoices are published; 0 third-party payments ever matched"},
    {"rail": "moltjobs", "status": "BID ONLY ON funded:true", "checked": False,
     "why": "escrowed USDC on Base; settlement goes to the custody wallet, not the payout address"},
    {"rail": "opentask", "status": "UNKNOWN", "checked": False,
     "why": "credential present, funding state not read in this run"},
    {"rail": "superteam earn", "status": "UNKNOWN", "checked": False,
     "why": "credential present, no funded listing verified in this run"},
]


def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def success_rate(progress):
    """paid / everything that ever tried. None when the rail has no history."""
    if not isinstance(progress, dict):
        return None
    paid = int(progress.get("paid") or 0)
    tried = sum(int(progress.get(k) or 0) for k in
                ("paid", "rejected", "expired", "revising", "delivered", "accepted"))
    return round(paid / tried, 3) if tried else None


def evaluate(opp):
    """(verdict, reasons) for one opportunity dict.

    Pure: the caller has already resolved gross, cost, funding and gates.
    """
    reasons = []
    gross = float(opp.get("gross_usd") or 0)
    cost = float(opp.get("cost_to_start_usd") or 0)
    net = round(gross - cost, 6)
    opp["net_usd"] = net
    if opp.get("reward_kind") != "escrow":
        reasons.append(f"reward is {opp.get('reward_kind')}, not money the rail holds")
        return "ignore", reasons
    if net <= 0:
        reasons.append(f"gross {gross} minus cost {cost} leaves {net}")
        return "loss", reasons
    if opp.get("needs_identity"):
        reasons.append("claim needs an identity only K can provide")
        return "needs_owner", reasons
    if not opp.get("claimable"):
        reasons.append("no open slot or the claim window is closed")
        return "watch", reasons
    reasons.append(f"pays {net} net, claimable now")
    return "act_now", reasons


def frantic_items():
    code, board = get(FRANTIC_BOARD)
    if code != 200 or not board:
        return [], {"rail": "frantic", "http": code, "error": "board unreachable"}
    rows = (board.get("board") or {}).get("open_bounties") or []
    items = []
    for b in rows:
        # The board item carries no posting_id; its api_url is the only reliable handle.
        path = b.get("api_url") or str(b.get("url") or "").replace("/bounties/", "/v1/bounties/")
        detail_url = FRANTIC_DETAIL.format(path=path)
        code, detail = get(detail_url)
        d = (detail or {}).get("bounty") or {}
        progress = d.get("claim_progress") or b.get("claim_slots") or {}
        claim = (b.get("actions") or {}).get("claim") or {}
        # A rebate is only paid after you spend your own money, so the price is not income.
        is_rebate = "rebate" in (b.get("title") or "").lower() or "back" in (b.get("title") or "").lower()
        item = {
            "rail": "frantic",
            "id": f"frantic:{b.get('number')}",
            "title": (b.get("title") or "")[:100],
            "url": "https://gofrantic.com" + str(b.get("url") or ""),
            "source_url": detail_url,
            "detail_http": code,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "gross_usd": float(b.get("price_usd") or 0),
            "cost_to_start_usd": float(b.get("price_usd") or 0) if is_rebate else 0.0,
            "reward_kind": "escrow" if b.get("funded") else "advertised",
            "needs_identity": claim.get("state") == "requires_identity",
            "claimable": bool(claim.get("available")) and (
                (b.get("claim_slots") or {}).get("available") or 0) > 0,
            "claim_progress": progress,
            "success_rate": success_rate(progress),
            "expires_at": d.get("claim_window_minutes"),
        }
        verdict, reasons = evaluate(item)
        item["verdict"], item["reasons"] = verdict, reasons
        items.append(item)
    return items, {"rail": "frantic", "http": code, "open": len(rows)}


def nonsynthetic_items():
    code, data = get(NONSYNTHETIC)
    if code != 200 or not data:
        return [], {"rail": "nonsynthetic", "http": code, "error": "board unreachable"}
    items = []
    for t in data.get("tasks", []):
        if str(t.get("state") or "open").lower() != "open":
            continue
        reward = t.get("effective_reward_usd") or t.get("reward_usd") or 0
        item = {
            "rail": "nonsynthetic",
            "id": f"ns:{t.get('id')}",
            "title": (t.get("title") or "")[:100],
            "url": "https://nonsynthetic.net/",
            "source_url": NONSYNTHETIC,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "gross_usd": float(reward or 0),
            "cost_to_start_usd": 0.0,
            # pool_funded is the only escrow flag this rail has; house credits are not cash.
            "reward_kind": ("escrow" if t.get("pool_funded")
                            else "credit" if t.get("house_funded") else "advertised"),
            "needs_identity": not bool(t.get("open_to_all")),
            "claimable": bool(t.get("claim_here")),
            "expires_at": t.get("claim_expires_at") or t.get("auto_release_at"),
        }
        verdict, reasons = evaluate(item)
        item["verdict"], item["reasons"] = verdict, reasons
        items.append(item)
    # The board answers with one page of 50 however it is asked, so `open` is a page size,
    # not the number of open tasks on the rail.
    return items, {"rail": "nonsynthetic", "http": code, "open": len(items),
                   "note": "one page of 50 per response; the rail exposes no cursor"}


PRIORITY = {"act_now": 0, "needs_owner": 1, "watch": 2, "loss": 3, "ignore": 4}


def rank(items):
    def key(i):
        return (PRIORITY.get(i["verdict"], 9), -(i.get("net_usd") or 0),
                -(i.get("success_rate") or 0))
    return sorted(items, key=key)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    items, sources = [], []
    for fn in (frantic_items, nonsynthetic_items):
        got, src = fn()
        items.extend(got)
        sources.append(src)
    ranked = rank(items)
    counts = {}
    for i in ranked:
        counts[i["verdict"]] = counts.get(i["verdict"], 0) + 1
    report = {
        "schema": "af.opportunities.v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "rails_not_counted": RAILS,
        "counts": counts,
        "cash_opportunities": counts.get("act_now", 0),
        "opportunities": ranked,
    }
    for i in ranked:
        if i["verdict"] in ("act_now", "needs_owner", "loss"):
            print(f"  {i['verdict']:11s} {i['rail']:12s} net={i['net_usd']:>9} "
                  f"rate={i['success_rate']} {i['title'][:50]} :: {'; '.join(i['reasons'])}")
    print("counts:", json.dumps(counts, sort_keys=True))
    print("act_now (money AF can take today):", report["cash_opportunities"])
    if a.write:
        Path(OUT).parent.mkdir(parents=True, exist_ok=True)
        Path(OUT).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""AF self-service — a vending machine. A payment arrives, the review unlocks. No human.

How a project pays without any account:
  1. AF gives each target a unique invoice amount: $15 plus a few cents derived from the token
     address. The amount itself is the reference, so a plain USDC transfer carries everything
     needed. No forms, no logins, no email.
  2. AF watches its own wallet for inbound USDC on Base (eth_getLogs, Transfer topic).
  3. On a match, AF pins the review, records the tx, and writes site/paid/index.json.

Nothing is counted until the transfer is confirmed in a mined block. If the RPC cannot be
reached, AF publishes nothing and says so.

Usage:
  python3 tools/af_selfserve.py --invoices            # print each target's exact amount
  python3 tools/af_selfserve.py --scan                # scan inbound payments
  python3 tools/af_selfserve.py --scan --write        # apply unlocks and write site/paid/
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

AF = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
RPC = ["https://base-rpc.publicnode.com", "https://mainnet.base.org", "https://base.drpc.org"]
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TIERS = {"base": 15.0, "multi_chain": 35.0, "pinned_promotion": 75.0}
# Gemini advice 2026-11-18: a deployer in launch week pays a micro-amount without thinking.
# 0.5 USDC for the pinned fix report, offered in the on-chain memo itself.
MICRO_TIER = {"id": "micro_fix", "usdc": 0.5}
LEDGER = "artifacts/payments/paid.json"


def rpc(method, params):
    last = None
    for host in RPC:
        try:
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
            req = urllib.request.Request(host, data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": "AF-selfserve"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.load(r)
            if "result" in j:
                return j["result"]
            if j.get("error"):
                last = RuntimeError(json.dumps(j["error"])[:160])
        except Exception as e:
            last = e
    raise RuntimeError(f"rpc {method}: {str(last)[:160]}")


def micro_amount(token: str) -> float:
    """The 0.5-USDC micro invoice, made unique per token (0.51..0.59).

    A flat 0.5 would be cheap but anonymous: two deployers paying 0.5 are indistinguishable.
    Keeping a one-cent suffix preserves the amount-as-order-id trick at micro scale.
    """
    cents = (int(token[:10], 16) % 9) + 1
    return round(MICRO_TIER["usdc"] + cents / 100, 2)


def invoice_amount(token: str, tier: str = "base") -> float:
    """A unique cents-suffix per token, so a plain USDC transfer identifies the report."""
    base = TIERS[tier]
    cents = (int(token[:10], 16) % 90) + 1  # 1..90 -> $0.01..$0.90
    return round(base + cents / 100, 2)


def invoices(targets):
    out = []
    for t in targets:
        amt = invoice_amount(t["address"])
        out.append({"token": t["address"], "symbol": (t.get("reads") or {}).get("symbol"),
                    "amount_usdc": amt, "tier": "base", "report": t.get("reportUrl")})
    return out


def load_paid():
    if os.path.exists(LEDGER):
        try:
            return json.load(open(LEDGER))
        except Exception:
            pass
    return {"schema": "af.payments.v1", "payments": []}


def scan_inbound(lookback_blocks=100000, window=5000):
    """USDC transfers to AF on Base. Topics: Transfer(from, to).

    Public Base RPCs reject a wide eth_getLogs range, so the scan is chunked. A window that
    silently returned nothing once cost a missed payment, so each chunk is retried on the next
    host before it is given up on.
    """
    latest = int(rpc("eth_blockNumber", []), 16)
    start = max(0, latest - lookback_blocks)
    topic_to = "0x" + "0" * 24 + AF[2:].lower()
    out = []
    for s in range(start, latest + 1, window):
        e = min(s + window - 1, latest)
        logs = rpc("eth_getLogs", [{"fromBlock": hex(s), "toBlock": hex(e), "address": USDC_BASE,
                                    "topics": [TRANSFER, None, topic_to]}]) or []
        for l in logs:
            out.append({"txHash": l["transactionHash"], "block": int(l["blockNumber"], 16),
                        "from": "0x" + l["topics"][1][-40:], "amount_usdc": round(int(l["data"], 16) / 1e6, 6)})
    return {"scannedToBlock": latest, "fromBlock": start, "transfers": out}


def main() -> int:
    tp = "site/outbound/targets.json"
    targets = json.load(open(tp)).get("targets") if os.path.exists(tp) else []
    if "--invoices" in sys.argv:
        invs = invoices(targets)
        for inv in invs:
            print(f"  {inv['symbol'] or inv['token'][:10]:12s} pay exactly {inv['amount_usdc']:.2f} USDC "
                  f"on Base -> {inv['report']}")
        if "--write" in sys.argv:
            os.makedirs("site/outbound", exist_ok=True)
            json.dump({"schema": "af.invoices.v1", "pay_to": AF, "asset": {"symbol": "USDC", "chain": "base",
                       "address": USDC_BASE}, "note": "The exact amount is the order reference. No account needed.",
                       "invoices": invs}, open("site/outbound/invoices.json", "w"), indent=1)
            print("wrote site/outbound/invoices.json")
        return 0

    res = scan_inbound()
    inv = {round(i["amount_usdc"], 2): i for i in invoices(targets)}
    # micro tier: the 0.5x amount offered inside the on-chain memo
    for t in targets:
        a = round(micro_amount(t["address"]), 2)
        inv.setdefault(a, {"token": t["address"], "symbol": (t.get("reads") or {}).get("symbol"),
                           "amount_usdc": a, "tier": MICRO_TIER["id"], "report": t.get("reportUrl")})
    paid = load_paid()
    seen = {p["txHash"] for p in paid["payments"]}
    print(f"scanned blocks {res['fromBlock']}..{res['scannedToBlock']} | inbound transfers: {len(res['transfers'])}")
    matched = 0
    for t in res["transfers"]:
        if t["txHash"] in seen:
            continue
        m = inv.get(round(t["amount_usdc"], 2))
        if not m:
            print(f"  unmatched transfer {t['amount_usdc']} USDC from {t['from'][:10]}.. tx {t['txHash'][:12]}..")
            continue
        entry = {**t, "matchedToken": m["token"], "symbol": m["symbol"], "tier": m["tier"],
                 "at": datetime.now(timezone.utc).isoformat(),
                 "confirmed": True, "evidence": f"base tx {t['txHash']} in block {t['block']}"}
        paid["payments"].append(entry)
        matched += 1
        print(f"  MATCH {m['symbol'] or m['token'][:10]} <- {t['amount_usdc']} USDC (tx {t['txHash'][:12]}..)")
        if "--write" in sys.argv:
            key = f"base-{m['token'].lower()}"
            rp = f"site/reviews/{key}.json"
            if os.path.exists(rp):
                rep = json.load(open(rp))
                rep["pinned"] = True
                rep["pinnedAt"] = entry["at"]
                rep["paymentTx"] = t["txHash"]
                rep["tier"] = m["tier"]
                json.dump(rep, open(rp, "w"), indent=1)
                print(f"    pinned {rp}")
    if matched == 0:
        print("no new payments matched")
    if "--write" in sys.argv:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        json.dump(paid, open(LEDGER, "w"), indent=1)
        os.makedirs("site/paid", exist_ok=True)
        json.dump({"schema": "af.paid.index.v1", "count": len(paid["payments"]),
                   "cash_received_usdc": round(sum(p["amount_usdc"] for p in paid["payments"]), 6),
                   "payments": paid["payments"]}, open("site/paid/index.json", "w"), indent=1)
        print(f"wrote site/paid/index.json ({len(paid['payments'])} payments)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

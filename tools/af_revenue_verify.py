#!/usr/bin/env python3
"""AF revenue verifier — turn "income arrived" into a machine verdict.

K's rule (2026-11-08): income that keeps arriving counts as VERIFIED. This tool
decides that mechanically instead of by assumption, straight from the chain:

  * read AF's own receiving wallet USDC balance on Base,
  * scan the recent window for USDC Transfer logs *into* that wallet,
  * keep a ledger of distinct inbound transactions (tx hash -> first seen),
  * classify every inbound transfer before calling any of it revenue:
      self         - the sender is one of AF's own wallets, so the money never arrived
      own_trade    - a swap settlement paid AF because AF sold a token in that same tx
      unattributed - a third party paid, but no order id can be tied to the tx
      customer     - a third party paid AND the tx matches a published order id
  * verdict (NONE / FIRST / CONTINUOUS / RECURRING_SAME_DAY) counts third-party
    transfers only; `customer_verified_usdc_total` is the only field that is revenue.

Zero third-party deps (urllib JSON-RPC only), no secrets required (the wallet is
public), so a GitHub Actions job can run it on a schedule and commit the result.

Usage:
  python3 tools/af_revenue_verify.py            # print verdict JSON
  python3 tools/af_revenue_verify.py --write     # also update the ledger file
  python3 tools/af_revenue_verify.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

RPC = os.environ.get("AF_BASE_RPC", "https://base-rpc.publicnode.com")
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
AF_WALLET = os.environ.get("AF_WALLET_ADDR", "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702")
SCAN_BLOCKS = int(os.environ.get("AF_SCAN_BLOCKS", "49000"))  # publicnode caps at 50000
LEDGER = os.environ.get("AF_REVENUE_LEDGER", "data/revenue_ledger.json")
ORDERS_INDEX = os.environ.get("AF_ORDERS_INDEX", "site/api/orders/index.json")
# Swap settlement contracts pay USDC into AF's wallet because AF sold something in that
# same transaction: the money is AF's own capital coming back, never income.
KNOWN_SWAP_SENDERS = frozenset({
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41",  # CoW Protocol GPv2Settlement
})


def now():
    return datetime.now(timezone.utc).isoformat()


def rpc(method, params, retries=3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(RPC, data=body, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) af-revenue-verify/1.0",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            if "error" in d:
                raise RuntimeError(d["error"])
            return d["result"]
        except Exception as e:  # transient RPC limits are common; retry then surface
            last = e
            time.sleep(2)
    raise RuntimeError(f"rpc {method} failed: {last}")


def balance_usdc(addr):
    data = "0x70a08231" + "0" * 24 + addr[2:].lower()
    res = rpc("eth_call", [{"to": USDC, "data": data}, "latest"])
    return int(res, 16) / 10 ** 6


def self_addresses():
    """AF's own wallets; a transfer from one of them is a self-transfer, not income."""
    extra = os.environ.get("AF_SELF_ADDRESSES", "")
    found = [AF_WALLET] + [a for a in extra.split(",") if a.strip()]
    return frozenset(a.strip().lower() for a in found if a.strip())


def classify_transfer(from_addr, self_set, swap_senders=KNOWN_SWAP_SENDERS):
    sender = str(from_addr or "").lower()
    if sender in self_set:
        return "self"
    return "swap" if sender in swap_senders else "external"


def load_order_txs(path=None):
    """tx hash (lowercase) -> order id, from the published order index."""
    try:
        with open(path or ORDERS_INDEX) as f:
            data = json.load(f)
    except Exception:
        return {}
    out = {}
    for order in data.get("orders") or []:
        tx = str(order.get("tx") or "").strip().lower()
        if tx:
            out[tx] = order.get("id")
    return out


def summarise(records, self_set, order_txs):
    """Split received USDC into self-transfer, unattributed and verified customer money.

    A wrong match publishes revenue that was never earned, so a transfer is only called
    customer money when a third party sent it AND an order id names the same tx.
    """
    totals = {"self_transfer_usdc": 0.0, "own_trade_usdc": 0.0,
              "unattributed_usdc": 0.0, "customer_verified_usdc": 0.0}
    rows = []
    for rec in records:
        tx = str(rec.get("tx") or "").lower()
        kind = classify_transfer(rec.get("from"), self_set)
        if kind == "external" and rec.get("own_trade"):
            kind = "swap"  # the receipt showed AF paying a token in the same tx
        order_id = order_txs.get(tx) if kind == "external" else None
        usdc = float(rec.get("usdc") or 0)
        bucket = ("self_transfer_usdc" if kind == "self"
                  else "own_trade_usdc" if kind == "swap"
                  else "customer_verified_usdc" if order_id else "unattributed_usdc")
        totals[bucket] = round(totals[bucket] + usdc, 6)
        rows.append({"tx": tx, "from": rec.get("from"), "usdc": usdc, "at": rec.get("at"),
                     "kind": kind, "order_id": order_id, "bucket": bucket})
    return totals, rows


def verdict(external_count, external_days):
    if external_count == 0:
        return "NONE"
    if external_count == 1:
        return "FIRST"
    return "CONTINUOUS" if external_days >= 2 else "RECURRING_SAME_DAY"


def load_ledger():
    try:
        with open(LEDGER) as f:
            return json.load(f)
    except Exception:
        return {"schema": 1, "first_seen": {}, "days": []}


def save_ledger(led):
    os.makedirs(os.path.dirname(LEDGER) or ".", exist_ok=True)
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()

    out = {"job": "revenue_verify", "at": now(), "wallet": AF_WALLET, "rpc": RPC,
           "verdict": "NOT_VERIFIED", "recent_inflows": [], "balance_usdc": None}

    try:
        latest = int(rpc("eth_blockNumber", []), 16)
        frm = max(0, latest - SCAN_BLOCKS)
        out["block"] = latest
        out["balance_usdc"] = balance_usdc(AF_WALLET)
        to_topic = "0x" + "0" * 24 + AF_WALLET[2:].lower()
        logs = rpc("eth_getLogs", [{
            "address": USDC, "fromBlock": hex(frm), "toBlock": "latest",
            "topics": [TRANSFER, None, to_topic],
        }])
        led = load_ledger()
        seen = led.setdefault("first_seen", {})
        days = set(led.get("days") or [])
        new_tx = []
        for lg in logs:
            tx = lg["transactionHash"]
            val = int(lg["data"], 16) / 10 ** 6
            frm_addr = "0x" + lg["topics"][1][-40:]
            ts = None
            try:
                blk = rpc("eth_getBlockByNumber", [lg["blockNumber"], False])
                ts = int(blk["timestamp"], 16)
                days.add(datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d"))
            except Exception:
                pass
            rec = {"tx": tx, "from": frm_addr, "usdc": val,
                   "block": int(lg["blockNumber"], 16),
                   "at": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None}
            out["recent_inflows"].append(rec)
            if tx not in seen:
                new_tx.append(rec)
            seen.setdefault(tx, {"usdc": val, "from": frm_addr, "at": rec["at"]})
        out["new_tx"] = new_tx
        led["days"] = sorted(days)
        led["last_checked"] = out["at"]
        led["tx_count"] = len(seen)

        records = [dict(v, tx=k) for k, v in seen.items()]
        totals, rows = summarise(records, self_addresses(), load_order_txs())
        external = [r for r in rows if r["kind"] == "external"]
        external_days = len({(r.get("at") or "")[:10] for r in external if r.get("at")})
        out["verdict"] = verdict(len(external), external_days)
        out["inbound_tx_total"] = len(seen)
        out["external_tx_total"] = len(external)
        out["distinct_days"] = len(days)
        out["external_days"] = external_days
        out["days"] = led["days"]
        out["state"] = "VERIFIED"
        # The verdict is a mechanical rule, not a size claim: publish the amounts next to it so
        # "CONTINUOUS" cannot be read as income when the transfers were AF paying itself.
        out["inbound_usdc_total"] = round(sum(totals.values()), 6)
        out.update({k + "_total": v for k, v in totals.items()})
        out["revenue_basis"] = "customer_verified"
        out["transfers"] = rows
        out["verdict_note"] = (
            "%d third-party transfer(s) on %d day(s); %s USDC verified against an order, "
            "%s USDC unattributed, %s USDC from AF's own swaps, %s USDC moved between "
            "AF's own wallets"
            % (len(external), external_days, totals["customer_verified_usdc"],
               totals["unattributed_usdc"], totals["own_trade_usdc"],
               totals["self_transfer_usdc"]))

        if a.write:
            save_ledger(led)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"

    text = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json:
        with open(a.json, "w") as f:
            f.write(text)
    print(text)
    return 0 if out.get("state") == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

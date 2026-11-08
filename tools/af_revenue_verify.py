#!/usr/bin/env python3
"""AF revenue verifier — turn "income arrived" into a machine verdict.

K's rule (2026-11-08): income that keeps arriving counts as VERIFIED. This tool
decides that mechanically instead of by assumption, straight from the chain:

  * read AF's own receiving wallet USDC balance on Base,
  * scan the recent window for USDC Transfer logs *into* that wallet,
  * keep a ledger of distinct inbound transactions (tx hash -> first seen),
  * verdict:
      NONE       - no inbound transfer ever seen
      FIRST      - exactly one inbound transfer seen
      CONTINUOUS - >= 2 distinct inbound transfers on >= 2 distinct UTC days

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

        n = len(seen)
        distinct_days = len(days)
        if n == 0:
            out["verdict"] = "NONE"
        elif n == 1:
            out["verdict"] = "FIRST"
        elif distinct_days >= 2:
            out["verdict"] = "CONTINUOUS"
        else:
            out["verdict"] = "RECURRING_SAME_DAY"
        out["inbound_tx_total"] = n
        out["distinct_days"] = distinct_days
        out["days"] = led["days"]
        out["state"] = "VERIFIED"

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

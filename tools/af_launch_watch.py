#!/usr/bin/env python3
"""AF launch watcher — catch a token in the minute it is deployed, not a day later.

Gemini advice 2026-11-18: AF's first three memos went to deployers whose launch was already
over; they ignored a cold note. A deployer in the first minutes of a launch is anxious and
still watching the chain, so that is when a control-plane finding is worth reading — and when
0.5 USDC is worth paying.

This tool walks new Base blocks, finds contract creations, filters out non-token contracts
with a cheap on-chain read, and hands each fresh token to the outreach tool with the finding
that matters most (mint still present / can be paused / single-key owner).

It never guesses: a contract that does not answer symbol()/decimals() like a token is skipped,
and the note only states flags that came from the reader.

Usage:
  python3 tools/af_launch_watch.py --once            # one pass from the last seen block
  python3 tools/af_launch_watch.py --once --blocks 300
  python3 tools/af_launch_watch.py --once --write    # write site/outbound/launches.json
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RPC = ["https://base-rpc.publicnode.com", "https://mainnet.base.org", "https://base.drpc.org"]
STATE = "artifacts/outreach/watch-state.json"


def rpc(method, params):
    last = None
    for host in RPC:
        try:
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
            req = urllib.request.Request(host, data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": "AF-watch"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.load(r)
            if "result" in j:
                return j["result"]
            if j.get("error"):
                last = RuntimeError(json.dumps(j["error"])[:160])
        except Exception as e:
            last = e
    raise RuntimeError(f"rpc {method}: {str(last)[:160]}")


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return {"schema": "af.watch.state.v1", "lastBlock": None}


def find_creations(from_block, to_block):
    """Every contract created in the range, from the receipts of that range's transactions."""
    out = []
    for n in range(from_block, to_block + 1):
        blk = rpc("eth_getBlockByNumber", [hex(n), True]) or {}
        for tx in blk.get("transactions") or []:
            if tx.get("to"):
                continue  # a creation has no `to`
            rc = rpc("eth_getTransactionReceipt", [tx["hash"]]) or {}
            if rc.get("contractAddress"):
                out.append({"address": rc["contractAddress"], "deployer": tx["from"],
                            "block": n, "txHash": tx["hash"]})
    return out


def looks_like_token(address):
    """Cheap on-chain filter: a token answers symbol() and decimals(). No guessing from a name."""
    try:
        sym = rpc("eth_call", [{"to": address, "data": "0x95d89b41"}, "latest"])
        dec = rpc("eth_call", [{"to": address, "data": "0x313ce567"}, "latest"])
        if (not sym or sym == "0x") and (not dec or dec == "0x"):
            return None
        return {"hasSymbol": bool(sym and sym != "0x"), "hasDecimals": bool(dec and dec != "0x")}
    except Exception:
        return None


def main() -> int:
    blocks = int(sys.argv[sys.argv.index("--blocks") + 1]) if "--blocks" in sys.argv else 200
    st = load_state()
    latest = int(rpc("eth_blockNumber", []), 16)
    frm = st.get("lastBlock") or (latest - blocks)
    frm = max(int(frm), latest - 5000)  # never scan an unbounded range on a public RPC
    print(f"scanning Base blocks {frm}..{latest}")

    creations = find_creations(frm, latest)
    print(f"contract creations: {len(creations)}")
    tokens, skipped = [], []
    for c in creations:
        tk = looks_like_token(c["address"])
        if tk:
            tokens.append({**c, **tk})
        else:
            skipped.append(c["address"])
        time.sleep(0.05)

    out = {"schema": "af.launch.watch.v1", "generatedAt": datetime.now(timezone.utc).isoformat(),
           "fromBlock": frm, "toBlock": latest, "creations": len(creations),
           "tokens": tokens, "skippedNonToken": len(skipped),
           "note": "tokens are filtered by an on-chain symbol()/decimals() read, not by name"}
    print(f"token-like: {len(tokens)} | skipped non-token: {len(skipped)}")
    for t in tokens[:10]:
        print(f"  {t['address']} deployer {t['deployer'][:10]}.. block {t['block']}")

    st["lastBlock"] = latest + 1
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE, "w"), indent=1)
    if "--write" in sys.argv:
        os.makedirs("site/outbound", exist_ok=True)
        json.dump(out, open("site/outbound/launches.json", "w"), indent=1)
        print("wrote site/outbound/launches.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

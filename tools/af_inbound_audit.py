#!/usr/bin/env python3
"""Complete inbound-USDC history for AF's wallet, classified the same way the verifier does.

`af_revenue_verify.py` only looks back `AF_SCAN_BLOCKS` (49k, the public RPC's cap), so a
payment older than the window is invisible and the published ledger under-reports what
actually arrived. This walks the whole range in chunks and reuses the verifier's split
(self / unattributed / customer-verified), so the two tools can never disagree.

Read-only: JSON-RPC `eth_getLogs` and `eth_getBlockByNumber`, no keys, no transactions.

Usage:
  python3 tools/af_inbound_audit.py                      # scan 52,000,000 -> latest
  python3 tools/af_inbound_audit.py --from-block 0 --json /tmp/inbound.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_revenue_verify as rv  # noqa: E402

CHUNK = 25000  # public RPCs throttle wide eth_getLogs ranges, so start modest


def scan(from_block, to_block, chunk=CHUNK):
    """Walk the range in chunks, halving the chunk whenever the RPC pushes back."""
    topic = "0x" + "0" * 24 + rv.AF_WALLET[2:].lower()
    found = []
    unavailable = []
    start = from_block
    while start <= to_block:
        end = min(start + chunk - 1, to_block)
        try:
            logs = rv.rpc("eth_getLogs", [{
                "address": rv.USDC, "fromBlock": hex(start), "toBlock": hex(end),
                "topics": [rv.TRANSFER, None, topic],
            }])
        except RuntimeError:
            if chunk > 2000:
                chunk //= 2
                continue
            # Some public nodes refuse logs for blocks older than their archive window.
            # Record the gap instead of pretending the history is complete.
            unavailable.append([start, end])
            start = end + 1
            continue
        for lg in logs:
            found.append({
                "tx": lg["transactionHash"].lower(),
                "from": "0x" + lg["topics"][1][-40:],
                "usdc": int(lg["data"], 16) / 10 ** 6,
                "block": int(lg["blockNumber"], 16),
            })
        start = end + 1
        time.sleep(0.15)
    return found, unavailable


def _sold_a_token(tx):
    """True when the same transaction shows AF sending a non-USDC token out.

    A swap pays USDC in because AF paid a token out, so the USDC is AF's own capital
    returning. Sender allowlists drift; the receipt is evidence.
    """
    af_topic = "0x" + "0" * 24 + rv.AF_WALLET[2:].lower()
    receipt = rv.rpc("eth_getTransactionReceipt", [tx])
    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if (len(topics) >= 3 and topics[0].lower() == rv.TRANSFER
                and topics[1].lower() == af_topic
                and log["address"].lower() != rv.USDC.lower()):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-block", type=int, default=52_000_000)
    ap.add_argument("--json")
    a = ap.parse_args()

    latest = int(rv.rpc("eth_blockNumber", []), 16)
    rows, unavailable = scan(a.from_block, latest)
    stamps = {}
    for r in rows:
        if r["usdc"] and r["from"].lower() not in rv.self_addresses():
            r["own_trade"] = _sold_a_token(r["tx"])
    for r in rows:
        if r["block"] not in stamps:
            blk = rv.rpc("eth_getBlockByNumber", [hex(r["block"]), False])
            stamps[r["block"]] = datetime.fromtimestamp(
                int(blk["timestamp"], 16), timezone.utc).isoformat()
        r["at"] = stamps[r["block"]]

    totals, transfers = rv.summarise(rows, rv.self_addresses(), rv.load_order_txs())
    external = [t for t in transfers if t["kind"] == "external"]
    days = len({(t.get("at") or "")[:10] for t in external if t.get("at")})
    out = {
        "wallet": rv.AF_WALLET,
        "scanned": {"from_block": a.from_block, "to_block": latest},
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "unavailable_ranges": unavailable,
        "inbound_tx_total": len(transfers),
        "external_tx_total": len(external),
        "external_days": days,
        "verdict": rv.verdict(len(external), days),
        "revenue_basis": "customer_verified",
        **{k + "_total": v for k, v in totals.items()},
        "transfers": sorted(transfers, key=lambda t: t.get("block") or 0),
    }
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json:
        Path(a.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

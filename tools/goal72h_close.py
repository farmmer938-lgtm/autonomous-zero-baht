#!/usr/bin/env python3
"""Close the 72-hour goal from the chain, without a sandbox.

The goal: one payment >= 0.05 USDC on Base to AF from someone who is not AF and not K,
by GOAL_DEADLINE. A goal that nobody closes is not a goal, and a sandbox cannot be the
thing that closes it — the sandbox is recycled. This runs from GitHub Actions, reads the
chain, and writes the verdict to the repo. It passes as soon as a qualifying payment is
confirmed; if the deadline passes with none, it fails and says so.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import af_selfserve as ss

GOAL_ID = "m938-2.goal72h"
GOAL_DEADLINE = "2026-11-29T14:00:00Z"
MIN_USDC_UNITS = 50_000          # 0.05 USDC, 6 decimals
MIN_CONFIRMATIONS = 12
GOAL_START_BLOCK = 62_860_000    # first block at/after 2026-11-27T00:00Z
K_WALLET = "0xf007a2404b590cb8632abd1f52f8a42bd1c42303"
CHUNK = 25_000


def _hex_addr(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def scan(start_block: int, end_block: int | None = None) -> list[dict]:
    """USDC transfers into AF's wallet, oldest first. An RPC failure raises."""
    tip = int(ss.rpc("eth_blockNumber", []), 16) if end_block is None else end_block
    af = ss.AF.lower()
    out: list[dict] = []
    lo = start_block
    while lo <= tip:
        hi = min(lo + CHUNK - 1, tip)
        logs = ss.rpc("eth_getLogs", [{
            "fromBlock": hex(lo), "toBlock": hex(hi), "address": ss.USDC_BASE,
            "topics": [ss.TRANSFER, None, "0x" + "0" * 24 + af[2:]],
        }])
        for lg in logs:
            out.append({
                "tx": lg["transactionHash"],
                "block": int(lg["blockNumber"], 16),
                "units": int(lg["data"], 16),
                "usdc": int(lg["data"], 16) / 1e6,
                "from": _hex_addr(lg["topics"][1]),
            })
        lo = hi + 1
    return sorted(out, key=lambda t: t["block"])


def verdict(now: datetime | None = None, start_block: int = GOAL_START_BLOCK,
            transfers: list[dict] | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    deadline = datetime.fromisoformat(GOAL_DEADLINE.replace("Z", "+00:00"))
    if transfers is None:
        tip = int(ss.rpc("eth_blockNumber", []), 16)
        transfers = scan(start_block, end_block=tip)
    else:
        tip = max((t["block"] for t in transfers), default=start_block)
    transfers = sorted(transfers, key=lambda t: t["block"])

    excluded, qualified = [], []
    for t in transfers:
        if t["from"] in (ss.AF.lower(), K_WALLET):
            excluded.append({**t, "why": "payer is AF or K"})
        elif t["units"] < MIN_USDC_UNITS:
            excluded.append({**t, "why": f"below {MIN_USDC_UNITS} units"})
        else:
            qualified.append(t)

    base = {
        "schema": "af.goal72h_verdict.v1",
        "goal": GOAL_ID,
        "deadline": GOAL_DEADLINE,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pass_test": ("payer is not AF and not K, >= 0.05 USDC confirmed on Base to "
                      f"{ss.AF}"),
        "scan": {"from_block": start_block, "to_block": tip},
        "transfers_seen": len(transfers),
        "excluded": excluded,
    }
    if qualified:
        first = qualified[0]
        return {**base, "status": "PASS", "tx": first["tx"], "payer": first["from"],
                "amount_usdc": first["usdc"], "block": first["block"],
                "qualified": qualified,
                "note": "a stranger paid; the goal is met and closes here"}
    if now >= deadline:
        return {**base, "status": "FAIL", "payer_count": 0,
                "note": "deadline passed with no qualifying payment"}
    return {**base, "status": "OPEN", "payer_count": 0,
            "hours_left": round((deadline - now).total_seconds() / 3600, 1)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Chain-truth verdict for the 72h goal.")
    ap.add_argument("--json", default="", help="write the verdict here (default: stdout)")
    ap.add_argument("--now", default="", help="ISO timestamp, for tests")
    args = ap.parse_args(argv)
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    try:
        v = verdict(now=now)
    except Exception as e:  # an unreadable chain is not a verdict
        v = {"schema": "af.goal72h_verdict.v1", "goal": GOAL_ID, "status": "UNREADABLE",
             "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "reason": f"{type(e).__name__}: {e}"}
    text = json.dumps(v, ensure_ascii=False, indent=1) + "\n"
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

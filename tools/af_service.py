#!/usr/bin/env python3
"""AF service desk — the order book for a business with no human in the loop.

A buyer (agent or human) opens a GitHub issue with the fact they need. This tool:
  1. reads the open requests from the public issues API,
  2. scans AF's Base wallet for inbound USDC (chunked, public RPC),
  3. matches each confirmed payment to a request by amount and time,
  4. writes site/facts/queue.json so anyone can see what is open, what is paid,
     and what AF has actually earned.

It never invents a payment: a request is marked paid only when a confirmed
on-chain USDC transfer into AF's wallet covers it. Anything ambiguous is reported
as unmatched rather than guessed.

Usage: python3 tools/af_service.py [--write] [--repo OWNER/NAME]
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

REPO = "farmmer938-lgtm/autonomous-zero-baht"
AF_WALLET = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
BASE_RPCS = ["https://base-rpc.publicnode.com", "https://mainnet.base.org"]
PRICE_USD = 0.005  # measured x402 market median; see artifacts/vendor_consult


def _get(url: str, token: str | None = None):
    h = {"User-Agent": "AF-service/1.0", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=40) as r:
        return json.load(r)


def _rpc(method: str, params: list, host: str):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(host, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "AF-service/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def requests(repo: str, token: str | None = None) -> list[dict]:
    """Open issues that ask for a fact. A request is any open issue whose title
    starts with 'Fact request' or that carries the af-request label."""
    out = []
    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100"
    for it in _get(url, token):
        if "pull_request" in it:
            continue
        labels = {l["name"].lower() for l in it.get("labels", [])}
        title = (it.get("title") or "")
        if not (title.lower().startswith("fact request") or "af-request" in labels):
            continue
        body = it.get("body") or ""
        m = re.search(r"0x[a-fA-F0-9]{40}", body)
        chain = "base"
        for c in ("ethereum", "base", "optimism", "arbitrum"):
            if c in body.lower():
                chain = c
                break
        out.append({"number": it["number"], "title": title, "url": it["html_url"],
                    "createdAt": it["created_at"], "address": m.group(0) if m else None,
                    "chain": chain, "body": body[:400]})
    return out


def inbound_payments(span_blocks: int = 43200, window: int = 5000) -> list[dict]:
    """Confirmed USDC transfers into AF's wallet on Base, newest last."""
    head = None
    for h in BASE_RPCS:
        try:
            head = int(_rpc("eth_blockNumber", [], h), 16)
            break
        except Exception:
            continue
    if head is None:
        return []
    topic = "0x" + "0" * 24 + AF_WALLET[2:].lower()
    found = []
    for s in range(max(0, head - span_blocks), head + 1, window):
        e = min(s + window - 1, head)
        for h in BASE_RPCS:
            try:
                logs = _rpc("eth_getLogs", [{"address": USDC_BASE, "topics": [TRANSFER, None, topic],
                                             "fromBlock": hex(s), "toBlock": hex(e)}], h)
                for l in logs or []:
                    found.append({"tx": l["transactionHash"], "block": int(l["blockNumber"], 16),
                                  "from": "0x" + l["topics"][1][-40:], "usdc": int(l["data"], 16) / 1e6})
                break
            except Exception:
                continue
    found.sort(key=lambda x: x["block"])
    return found


def reconcile(reqs: list[dict], pays: list[dict], block_time=None):
    """Match payments to requests on evidence, never on a guess.

    Two matches are accepted, strongest first:
      1. the request names the payment's tx hash in its body;
      2. exactly one claimable payment and exactly one unpaid request exist.
    Everything else stays unpaid and is reported as an unmatched payment, because a
    wrong match publishes revenue that was never earned.
    """
    for r in reqs:
        r["priceUsd"] = PRICE_USD
        r["paid"] = False
        r["tx"] = None
        r["matchMethod"] = None
        r["claimedTxHashes"] = sorted(_tx_hashes(r.get("body", "")))
    used: set[int] = set()

    def claim(r, index, method):
        p = pays[index]
        used.add(index)
        r["paid"] = True
        r["tx"] = p["tx"]
        r["paidUsdc"] = p["usdc"]
        r["paidBlock"] = p["block"]
        r["matchMethod"] = method

    def covers(index):
        return pays[index]["usdc"] + 1e-9 >= PRICE_USD

    for r in reqs:
        for i, p in enumerate(pays):
            if i in used or not covers(i):
                continue
            if p["tx"].lower() in r["claimedTxHashes"]:
                claim(r, i, "tx_hash_in_request")
                break

    unclaimed = [i for i in range(len(pays)) if i not in used and covers(i)]
    unpaid = [r for r in reqs if not r["paid"]]
    if len(unclaimed) == 1 and len(unpaid) == 1:
        paid_at = block_time(pays[unclaimed[0]]["block"]) if block_time else None
        if paid_at is None or _parse_iso(paid_at) >= _parse_iso(unpaid[0]["createdAt"]):
            claim(unpaid[0], unclaimed[0], "only_open_request_and_payment")

    for r in reqs:
        if not r["paid"] and unclaimed:
            r["matchNote"] = "payment(s) seen but no unambiguous match; add the tx hash to the issue"
    return reqs, [pays[i] for i in range(len(pays)) if i not in used]


def _tx_hashes(text: str) -> set[str]:
    return {m.group(0).lower() for m in re.finditer(r"0x[a-fA-F0-9]{64}", text or "")}


def _parse_iso(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def block_time_lookup():
    """Lazily read block timestamps so a payment older than its request cannot match."""
    cache: dict[int, str | None] = {}

    def lookup(block: int):
        if block not in cache:
            cache[block] = None
            for h in BASE_RPCS:
                try:
                    b = _rpc("eth_getBlockByNumber", [hex(block), False], h)
                    cache[block] = datetime.fromtimestamp(int(b["timestamp"], 16), timezone.utc).isoformat()
                    break
                except Exception:
                    continue
        return cache[block]

    return lookup


def build(repo: str, token: str | None) -> dict:
    reqs = requests(repo, token)
    pays = inbound_payments()
    reqs, unmatched = reconcile(reqs, pays, block_time=block_time_lookup())
    served = [r for r in reqs if r["paid"]]
    return {
        "schema": "af.service.queue.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "business": {
            "what": "AF verifies one control-plane fact per request and publishes it, block-pinned.",
            "price_usd": PRICE_USD,
            "how_to_request": f"Open an issue titled 'Fact request' at https://github.com/{repo}/issues/new "
                              "with the chain, the contract address and its docs URL.",
            "how_to_pay": f"Send {PRICE_USD} USDC on Base to {AF_WALLET}, then comment the tx hash on the issue.",
            "payout_address": AF_WALLET,
        },
        "open_requests": len(reqs) - len(served),
        "served": len(served),
        "revenue_usd": round(sum(r.get("paidUsdc", 0) for r in served), 6),
        "requests": reqs,
        "payments_seen": pays,
        "unmatched_payments": unmatched,
        "match_rules": ("A request is paid only when its issue names the tx hash, or when exactly one "
                        "open request and one claimable payment exist and the payment is not older "
                        "than the request. Anything else is reported as unmatched, not guessed."),
        "honest_state": ("A request counts as served only when a confirmed on-chain USDC transfer covers it. "
                         "Unmatched payments are listed as seen, not guessed. Zero requests means zero demand, "
                         "not zero capability."),
    }


def main() -> int:
    repo = REPO
    if "--repo" in sys.argv:
        repo = sys.argv[sys.argv.index("--repo") + 1]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
    q = build(repo, token)
    if "--write" in sys.argv:
        os.makedirs("site/facts", exist_ok=True)
        with open("site/facts/queue.json", "w") as fh:
            json.dump(q, fh, indent=1)
        print(f"wrote site/facts/queue.json: {q['open_requests']} open, {q['served']} served, ${q['revenue_usd']}")
    else:
        print(json.dumps(q, indent=1)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

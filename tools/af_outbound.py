#!/usr/bin/env python3
"""AF outbound — hunt brand-new Base tokens and build a transparency report for each.

The problem this solves: nobody pays for a review of USDC. A token that launched minutes
ago and has real liquidity needs proof of credibility *now*. AF finds those tokens, reads
their control plane from the chain, writes an honest report, and prepares a direct message
to the creator with a link to the report.

Sources (both public, no key):
  - GeckoTerminal  /networks/base/new_pools   -> pool age + reserve_in_usd
  - DexScreener    /latest/dex/tokens/{addr}  -> socials + websites (outreach handles)

Nothing is invented. If a source returns nothing, the run says so and publishes nothing.

Usage:
  python3 tools/af_outbound.py --scan                 # list targets, no writes
  python3 tools/af_outbound.py --scan --write         # write site/outbound/ + reports
  python3 tools/af_outbound.py --scan --hours 24 --min-liq 10000 --write
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from af_token_review import review, verdict  # noqa: E402

GT = "https://api.geckoterminal.com/api/v2"
GT_HDR = {"Accept": "application/json;version=20230302", "User-Agent": "AF-outbound"}
DEX = "https://api.dexscreener.com"
PAY = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"
SITE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht"
STABLES = {"USDC", "USDT", "DAI", "USDG", "USDS", "WETH", "ETH", "cbBTC", "CBBTC"}


def _get(url, hdr=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr or {"User-Agent": "AF-outbound"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 2 * i)  # GeckoTerminal 429s by shared IP
    return None


def new_pools(pages=3):
    out = []
    for p in range(1, pages + 1):
        d = _get(f"{GT}/networks/base/new_pools?page={p}", GT_HDR)
        if not d or "data" not in d:
            break
        out.extend(d["data"])
        time.sleep(4)  # pace: 429 is silent
    return out


def token_socials(address):
    d = _get(f"{DEX}/latest/dex/tokens/{address}")
    if not d or not d.get("pairs"):
        return {}
    # prefer the highest-liquidity pair
    p = max(d["pairs"], key=lambda x: ((x.get("liquidity") or {}).get("usd") or 0))
    info = p.get("info") or {}
    return {"symbol": (p.get("baseToken") or {}).get("symbol"),
            "name": (p.get("baseToken") or {}).get("name"),
            "priceUsd": p.get("priceUsd"), "fdv": p.get("fdv"),
            "liquidityUsd": (p.get("liquidity") or {}).get("usd"),
            "socials": info.get("socials") or [], "websites": info.get("websites") or [],
            "dexId": p.get("dexId"), "pairAddress": p.get("pairAddress"),
            "pairUrl": p.get("url")}


def scan(hours=24, min_liq=10000, max_targets=12, pages=8):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    pools = new_pools(pages=pages)
    seen, targets, skipped = set(), [], []
    for pool in pools:
        a = pool.get("attributes") or {}
        created = a.get("pool_created_at")
        liq = float(a.get("reserve_in_usd") or 0)
        if not created:
            continue
        try:
            t = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except Exception:
            continue
        if t < cutoff:
            continue
        name = a.get("name") or ""
        base_sym = name.split("/")[0].strip()
        if base_sym.upper() in STABLES:
            continue
        # the token address lives in relationships, not attributes
        addr = (((pool.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id") or ""
        addr = addr.split("_")[-1]
        if not addr.startswith("0x") or addr in seen:
            continue
        seen.add(addr)
        if liq < min_liq:
            skipped.append({"symbol": base_sym, "address": addr, "liquidityUsd": liq,
                            "why": f"liquidity ${liq:,.0f} below ${min_liq:,.0f} floor"})
            continue
        if len(targets) >= max_targets:
            break
        soc = token_socials(addr)
        rep = review("base", addr)
        rep["verdict"] = verdict(rep)
        rep["liquidityUsd"] = liq
        rep["poolCreatedAt"] = created
        rep["poolName"] = name
        rep["outreach"] = soc
        targets.append(rep)
        time.sleep(2)
    return {"schema": "af.outbound.scan.v1", "generatedAt": now.isoformat(),
            "network": "base", "windowHours": hours, "liquidityFloorUsd": min_liq,
            "poolsScanned": len(pools), "targets": targets, "skipped": skipped}


def outreach_message(rep):
    soc = rep.get("outreach") or {}
    sym = (rep.get("reads") or {}).get("symbol") or soc.get("symbol") or "your token"
    flags = rep.get("flags") or []
    lines = [
        f"Hi — AF here, an autonomous agent that reads token control planes from the chain.",
        f"I read {sym} ({rep['address']}) on Base at one finalized block. Public and reproducible:",
    ]
    for f in flags:
        lines.append(f"  - {f}")
    if not flags:
        lines.append("  - no owner() surface and no EIP-1967 upgrade slot were found")
    lines.append("")
    lines.append("AF only reports what the chain answered. It does not say a token is safe, and it never")
    lines.append("issues a buy or sell call — a missing owner() function is not the same as no mint function.")
    lines.append("")
    lines.append("A full review pins this report to a shareable URL and adds a clearly-labelled promotion:")
    lines.append("  $15 single-chain (Base) · $35 multi-chain · $75 with a pinned promotion post")
    lines.append("  Pay in USDC on Base, or in your own token at market value at the time we agree:")
    lines.append(f"  {PAY}")
    lines.append(f"Product page: {SITE}/reviews.html")
    return "\n".join(lines)


def main() -> int:
    hours = int(sys.argv[sys.argv.index("--hours") + 1]) if "--hours" in sys.argv else 24
    min_liq = int(sys.argv[sys.argv.index("--min-liq") + 1]) if "--min-liq" in sys.argv else 10000
    d = scan(hours=hours, min_liq=min_liq)
    print(f"pools scanned: {d['poolsScanned']} | targets: {len(d['targets'])} | skipped: {len(d['skipped'])}")
    for t in d["targets"]:
        rd = t.get("reads") or {}
        oc = t.get("outreach") or {}
        soc = ",".join(s.get("type", "?") for s in oc.get("socials") or []) or "-"
        print(f"  {rd.get('symbol') or oc.get('symbol') or '?':10s} liq=${t['liquidityUsd']:>12,.0f} "
              f"verdict={t.get('verdict'):42s} socials={soc}")
    if "--write" in sys.argv:
        os.makedirs("site/outbound", exist_ok=True)
        os.makedirs("site/reviews", exist_ok=True)
        published = []
        for t in d["targets"]:
            key = f"base-{t['address'].lower()}"
            with open(f"site/reviews/{key}.json", "w") as fh:
                json.dump(t, fh, indent=1)
            t["reportPath"] = f"reviews/{key}.json"
            t["reportUrl"] = f"{SITE}/reviews/{key}.json"
            t["message"] = outreach_message(t)
            published.append(t)
        d["targets"] = published
        with open("site/outbound/targets.json", "w") as fh:
            json.dump(d, fh, indent=1)
        with open("site/reviews/index.json", "w") as fh:
            json.dump({"schema": "af.reviews.index.v1", "count": len(published),
                       "reviews": [{"chain": "base", "address": t["address"],
                                    "symbol": (t.get("reads") or {}).get("symbol"),
                                    "verdict": t.get("verdict"), "flags": t.get("flags"),
                                    "path": t["reportPath"]} for t in published]}, fh, indent=1)
        print(f"wrote site/outbound/targets.json + {len(published)} report(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

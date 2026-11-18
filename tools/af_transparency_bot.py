#!/usr/bin/env python3
"""AF transparency bot — scan new Base tokens, publish a short honest note, attach the pay link.

AF has no X account and cannot post to Farcaster (posting needs an FID; registration is paid).
What AF CAN do without any gate is publish to Nostr. So this bot:

  1. runs the outbound scan (tools/af_outbound.py),
  2. writes a short, factual note per fresh token (what the chain answered, nothing more),
  3. publishes the note to Nostr with the pay link and the report URL,
  4. appends every note to site/outbound/bot-log.json so the run is auditable.

It never says a token is safe and never issues a buy or sell call.

Usage:
  python3 tools/af_transparency_bot.py --dry-run
  python3 tools/af_transparency_bot.py --publish --max 3
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht"
PAY = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"


def load_targets():
    path = "site/outbound/targets.json"
    if not os.path.exists(path):
        subprocess.run([sys.executable, os.path.join(HERE, "af_outbound.py"),
                        "--scan", "--hours", "24", "--min-liq", "10000", "--write"], check=False)
    with open(path) as fh:
        return json.load(fh)


def note_for(t: dict) -> str:
    rd = t.get("reads") or {}
    sym = rd.get("symbol") or (t.get("outreach") or {}).get("symbol") or "a new token"
    flags = t.get("flags") or []
    head = f"New on Base: {sym} ({t['address'][:10]}…). Pool is {t['poolCreatedAt'][:16]}Z, liquidity ${t['liquidityUsd']:,.0f}."
    body = "Chain read at one finalized block: " + ("; ".join(flags) if flags
            else "no owner() surface and no EIP-1967 upgrade slot found")
    tail = (f"I only report what the chain answered. This is not a buy or sell call, and it is not a claim that "
            f"{sym} is safe. Free report: {t.get('reportUrl')} — a full review plus a labelled promotion is $15 "
            f"({SITE}/reviews.html). Pay in USDC on Base or in the token at market value: {PAY}")
    return f"{head}\n\n{body}\n\n{tail}"


def publish_nostr(text: str):
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "af_nostr.py"), "publish", text],
                           capture_output=True, text=True, timeout=120)
        ok = r.returncode == 0 and "ok" in (r.stdout or "").lower()
        return {"ok": ok, "code": r.returncode, "out": (r.stdout or r.stderr or "")[-200:]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:150]}


def main() -> int:
    max_n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 3
    do_publish = "--publish" in sys.argv
    d = load_targets()
    targets = d.get("targets") or []
    print(f"targets available: {len(targets)} | will publish: {min(max_n, len(targets))} | publish={do_publish}")
    log_path = "site/outbound/bot-log.json"
    log = {"schema": "af.transparency.bot.v1", "runs": []}
    if os.path.exists(log_path):
        try:
            log = json.load(open(log_path))
        except Exception:
            pass
    run = {"at": datetime.now(timezone.utc).isoformat(), "published": []}
    for t in targets[:max_n]:
        text = note_for(t)
        print("-" * 60)
        print(text[:400])
        entry = {"address": t["address"], "symbol": (t.get("reads") or {}).get("symbol"), "note": text}
        if do_publish:
            entry["nostr"] = publish_nostr(text)
            print("  nostr:", entry["nostr"])
        run["published"].append(entry)
    log["runs"].append(run)
    log["runs"] = log["runs"][-30:]
    os.makedirs("site/outbound", exist_ok=True)
    with open(log_path, "w") as fh:
        json.dump(log, fh, indent=1)
    print(f"logged to {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

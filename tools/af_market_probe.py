#!/usr/bin/env python3
"""Search the nearby markets by the problem people state, not by our product name.

Three rules the classification follows, because "count the hits" is how a market study lies:

1. **A GitHub account of type `Bot` is a bot.** The API says so; no guesswork.
2. **A cast with an agent marker is an agent.** "[Autonomous Agent ...]", "🤖", an
   `-agent`/`bot` handle. Everything else is `unclear`, not `human` — AF cannot verify a
   person, so it does not claim one.
3. **Only `question_with_context` counts as demand**: a stated problem with a token or a
   contract in it, or an explicit ask. A keyword in a title is not a buyer.

Writes data/market_probe.json. Read-only: no account, no write, no scraping behind a login.

Usage: python3 tools/af_market_probe.py [--write]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_farcaster as fc  # noqa: E402

OUT = Path("data/market_probe.json")
AGENT_MARKERS = ("[autonomous agent", "🤖", "agent knowledge", "autonomous agent")
HANDLE_MARKERS = ("bot", "agent", "_ai", "ai_")
PROBLEM_MARKERS = ("mint", "renounce", "owner", "honeypot", "rug", "safe", "scam",
                   "upgrade", "audit", "verify")

GITHUB_QUERIES = [
    '"mint authority" is:issue',
    '"renounce ownership" is:issue',
    '"is this token safe" is:issue',
    '"honeypot" is:issue base',
    '"token audit" is:issue base',
]
FARCASTER_QUERIES = ["mint authority", "renounce ownership", "is this token safe",
                     "honeypot base token", "token audit"]


def classify_github_issue(item):
    """Bot-ness comes from the API, demand from the words. A bare keyword is `unclear`."""
    user = item.get("user") or {}
    title = (item.get("title") or "")
    body = (item.get("body") or "")
    text = f"{title} {body}".lower()
    if (user.get("type") or "").lower() == "bot" or user.get("login", "").endswith("[bot]"):
        return "bot"
    if "0x" in text or ("?" in title and any(m in text for m in PROBLEM_MARKERS)):
        return "question_with_context"
    return "unclear"


def classify_cast(cast):
    text = (cast.get("text") or "")
    low = text.lower()
    author = ((cast.get("author") or {}).get("username") or "").lower()
    if any(m in low for m in AGENT_MARKERS) or any(h in author for h in HANDLE_MARKERS):
        return "bot"
    if "?" in text and any(m in low for m in PROBLEM_MARKERS):
        return "question_with_context"
    return "unclear"


def tally(rows):
    counts = {"bot": 0, "question_with_context": 0, "unclear": 0}
    samples = []
    for r in rows:
        counts[r["kind"]] += 1
        if r["kind"] == "question_with_context":
            samples.append(r["sample"])
    return counts, samples[:5]


def gh(path, params):
    url = "https://api.github.com" + path + "?" + urllib.parse.urlencode(params)
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    req = urllib.request.Request(url, headers={
        "authorization": f"Bearer {tok}", "accept": "application/vnd.github+json",
        "user-agent": "af-market-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def github_market():
    out = []
    for q in GITHUB_QUERIES:
        d = gh("/search/issues", {"q": q, "per_page": 30, "sort": "created", "order": "desc"})
        items = d.get("items") or []
        rows = [{"kind": classify_github_issue(i),
                 "sample": f"{i.get('repository_url', '').split('/repos/')[-1]} "
                           f"#{i.get('number')} {i.get('title', '')[:70]}"} for i in items]
        counts, samples = tally(rows)
        out.append({"query": q, "total_indexed": d.get("total_count"),
                    "sampled": len(items), **counts, "samples": samples,
                    "error": d.get("_error")})
        print(f"GitHub {q}: total={d.get('total_count')} sampled={len(items)} "
              f"human_questions={counts['question_with_context']} bots={counts['bot']}")
    return out


def farcaster_market():
    out = []
    for q in FARCASTER_QUERIES:
        d = fc._get("/v2/search-casts", {"q": q.replace(" ", "%20"), "limit": 25})
        casts = ((d.get("result") or {}).get("casts") or []) if not d.get("_error") else []
        rows = [{"kind": classify_cast(c), "sample": (c.get("text") or "")[:70]} for c in casts]
        counts, samples = tally(rows)
        out.append({"query": q, "sampled": len(casts), **counts, "samples": samples,
                    "error": d.get("_error")})
        print(f"Farcaster {q}: sampled={len(casts)} "
              f"questions={counts['question_with_context']} bots={counts['bot']}")
    return out


SEGMENTS = [
    {"segment": "token creator who wants to look clean",
     "problem": "buyers ask them for proof of ownership / no-mint",
     "fits_today": "partial", "why": "AF reports the control surface; it refuses to certify, so it cannot give the assurance they are really buying"},
    {"segment": "Web3 developer reviewing a contract",
     "problem": "wants to know who can change what, at which block",
     "fits_today": "yes", "why": "this is exactly what the engine reads, and the hash makes it diffable"},
    {"segment": "user deciding whether to buy a token",
     "problem": "is the owner able to mint or rug",
     "fits_today": "yes", "why": "owner, owner type, supply and upgradeability answer the question; honeypot stays unread and is labelled so"},
    {"segment": "community moderator vetting a token before recommending it",
     "problem": "needs a citable artefact, not a green badge",
     "fits_today": "yes", "why": "a block-stamped, hashed report is exactly what a moderator can paste"},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    rec = {"schema": "af.market_probe.v1",
           "at": datetime.now(timezone.utc).isoformat(),
           "method": "GitHub search API (user.type gives bot truth) + Farcaster public "
                     "search, read-only, no account",
           "classification": {"bot": "API says Bot, or an agent marker in the text/handle",
                              "question_with_context": "a '?' plus a problem word, or an "
                                                       "address in the text",
                              "unclear": "everything else — never counted as a human"},
           "github": github_market(),
           "farcaster": farcaster_market(),
           "segments": SEGMENTS}
    tot = sum(q["question_with_context"] for q in rec["github"] + rec["farcaster"])
    rec["verified_demand_events"] = tot
    print("verified demand events (question with context):", tot)
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

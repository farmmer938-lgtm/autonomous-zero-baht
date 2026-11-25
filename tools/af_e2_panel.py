#!/usr/bin/env python3
"""E2 — ten audits of tokens that are actually being traded, published with no outreach.

Selection rule, stated exactly once: the top ten Base tokens by 24h pool volume in
GeckoTerminal's trending-pools list at the moment of the run. Volume is a proxy for *people are
trading this*, not proof that anyone wants an audit — the page says so in those words.

Each page carries the block, the reads, a sha256 of the underlying report, the list of what was
NOT established, and a paragraph on what the page cannot tell you. It never says safe, never
says honeypot, never predicts a price.

Usage:
  python3 tools/af_e2_panel.py --select            # choose and store the panel (no network audit)
  python3 tools/af_e2_panel.py --run               # audit the stored panel and write pages
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_case_study as cs  # noqa: E402
import af_token_review as tr  # noqa: E402

LEDGER = Path("data/e2_panel.json")
OUT = Path("site/audit/e2")
BASE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht/audit/e2/"
GECKO = "https://api.geckoterminal.com/api/v2/networks/base/trending_pools?page=1"
LIMIT = 10


def _get(url):
    req = urllib.request.Request(url, headers={"user-agent": "af-e2", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def candidates(payload):
    """GeckoTerminal payload -> token dicts, one per base token, keeping the deepest pool."""
    best = {}
    for p in payload.get("data") or []:
        a = p.get("attributes") or {}
        rel = ((p.get("relationships") or {}).get("base_token") or {}).get("data") or {}
        addr = (rel.get("id") or "").split("_")[-1].lower()
        if not addr.startswith("0x"):
            continue
        row = {"address": addr,
               "symbol": (a.get("name") or "?").split(" / ")[0].strip(),
               "pool_name": a.get("name"),
               "pool_address": a.get("address"),
               "h24_volume_usd": float((a.get("volume_usd") or {}).get("h24") or 0),
               "liquidity_usd": float(a.get("reserve_in_usd") or 0),
               "source_url": ("https://www.geckoterminal.com/base/pools/" +
                              str(a.get("address")))}
        old = best.get(addr)
        if not old or row["h24_volume_usd"] > old["h24_volume_usd"]:
            best[addr] = row
    return sorted(best.values(), key=lambda r: -r["h24_volume_usd"])


def select(rows, limit=LIMIT):
    """Deterministic: highest 24h volume first, deduped by address."""
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: (-x["h24_volume_usd"], x["address"])):
        if r["address"] in seen:
            continue
        seen.add(r["address"])
        out.append(r)
        if len(out) == limit:
            break
    return out


def slug(row):
    return "%s-%s" % ("".join(ch for ch in row["symbol"].lower() if ch.isalnum())[:12] or "token",
                      row["address"][2:10])


def build(row, now=None):
    now = now or datetime.now(timezone.utc)
    rep = tr.review("base", row["address"])
    reads = rep.get("reads") or {}
    return {
        "schema": "af.e2.token.v1",
        "slug": slug(row),
        "at": now.isoformat(),
        "chain": "base",
        "address": row["address"],
        "symbol": reads.get("symbol") or row["symbol"],
        "name": reads.get("name"),
        "why_here": ("top %d Base token by 24h pool volume in GeckoTerminal's trending list when "
                     "this page was generated" % LIMIT),
        "selection_evidence": {k: row.get(k) for k in ("h24_volume_usd", "liquidity_usd",
                                                       "pool_name", "pool_address", "source_url")},
        "block": rep.get("blockNumber"),
        "verdict": tr.verdict(rep),
        "read": {k: reads.get(k) for k in ("symbol", "name", "decimals", "totalSupplyTokens",
                                          "owner", "ownerKind", "isMintable", "isUpgradeable",
                                          "bytecodeScannedAddress") if k in reads},
        "flags": rep.get("flags") or [],
        "not_established": reads.get("notChecked") or [],
        "errors": rep.get("errors") or [],
        "free_scanner": cs.goplus(row["address"]),
        "report_path": "site/reviews/base-%s.json" % row["address"],
        "report_sha256": hashlib.sha256(json.dumps(rep, sort_keys=True).encode()).hexdigest(),
    }


def _v(x, dash="not returned"):
    return dash if x is None or x == "" else html.escape(str(x))


def render(case):
    ev = case["selection_evidence"]
    sc = case["free_scanner"] or {}
    read_rows = "".join(f"<tr><td>{html.escape(k)}</td><td><code>{_v(v)}</code></td></tr>"
                        for k, v in case["read"].items())
    flags_html = "".join(f"<li><code>{html.escape(str(f))}</code></li>"
                         for f in case.get("flags") or [])
    not_rows = "".join(f"<li>{html.escape(str(x))}</li>" for x in case["not_established"]) \
        or "<li>the report lists no unchecked fields; treat that as a data gap, not a clean bill</li>"
    sc_rows = "".join(f"<tr><td>{html.escape(k)}</td><td><code>{_v(v)}</code></td></tr>"
                      for k, v in sc.items()) or "<tr><td colspan=2>free scanner did not answer</td></tr>"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_v(case['symbol'])} — what the chain says about control, at block {_v(case['block'])}</title>
<meta name="description" content="Owner, mint authority and upgradeability of {_v(case['symbol'])} on Base, read at block {_v(case['block'])}, with a sha256 and a list of what was not checked.">
<link rel="canonical" href="{BASE}{case['slug']}.html">
<style>body{{font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:820px;margin:0 auto;padding:24px 18px;background:#0b0d12;color:#e8ecf4}}a{{color:#4f8cff}}code{{font-family:ui-monospace,monospace;font-size:13px;word-break:break-all}}table{{border-collapse:collapse;width:100%;margin:12px 0}}td,th{{border:1px solid #232838;padding:6px 8px;text-align:left;vertical-align:top}}.mut{{color:#9aa4b8}}.warn{{border-left:3px solid #ffb020;padding-left:12px}}</style>
</head><body>
<p class="mut"><a href="../../audit/">← all audits</a> · generated {html.escape(case['at'][:19])}Z</p>
<h1>{_v(case['symbol'])} on Base</h1>
<p>Contract <code>{_v(case['address'])}</code>, read at block <code>{_v(case['block'])}</code>.
Verdict: <strong>{_v(case['verdict'])}</strong>.</p>
<p class="mut">Why this token is here: {html.escape(case['why_here'])} —
{ev.get('h24_volume_usd', 0):,.0f} USD of 24h volume, {ev.get('liquidity_usd', 0):,.0f} USD of
liquidity. Volume means people are trading it. It does not mean anyone wants an audit.</p>
<h2>What was read</h2>
<table><tr><th>field</th><th>value at block {_v(case['block'])}</th></tr>{read_rows}</table>
<h2>What this page cannot tell you</h2>
<div class="warn">
<ul>
<li>It says nothing about whether you can sell this token. No swap was simulated and no
honeypot test was performed — that needs capital this project does not have.</li>
<li>It is not a safety certification, a rating, a score, or investment advice.</li>
<li>It does not predict the price, the liquidity, or whether the owner will act.</li>
</ul>
</div>
<h2>What the bytecode scan flagged</h2>
<ul>{flags_html or "<li>nothing was flagged. That is not the same as nothing being present — "
                   "the scan only checks the selectors it knows.</li>"}</ul>
<h2>What was deliberately not established</h2>
<ul>{not_rows}</ul>
<h2>What the free scanner says about the same address</h2>
<table><tr><th>field</th><th>quoted value</th></tr>{sc_rows}</table>
<p class="mut">Quoted, not interpreted. Where the two disagree, the chain read above is the one
with a block number attached, and this page does not claim it is the more complete answer.</p>
<h2>Reproduce it</h2>
<p>Raw report: <code>{_v(case['report_path'])}</code> ·
sha256 of the report JSON: <code>{case['report_sha256']}</code></p>
<p class="mut">Errors during the read: {_v(', '.join(case['errors']) or 'none')}</p>
</body></html>
"""


def render_index(cases, now):
    rows = "".join(
        f"<tr><td><a href=\"{c['slug']}.html\">{_v(c['symbol'])}</a></td>"
        f"<td><code>{c['address'][:10]}…</code></td><td>{_v(c['verdict'])}</td>"
        f"<td>{_v(c['block'])}</td>"
        f"<td>{'; '.join(html.escape(str(f)) for f in c.get('flags') or []) or 'none flagged'}</td></tr>"
        for c in cases)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ten Base tokens, read at their block — an audit panel</title>
<meta name="description" content="Ten Base tokens chosen by 24h trading volume, each with its control surface read at a named block and a list of what was not checked.">
<link rel="canonical" href="{BASE}">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"ItemList","name":"Ten Base tokens, read at their block","itemListElement":[{",".join('{"@type":"ListItem","position":%d,"url":"%s%s.html"}' % (i + 1, BASE, c["slug"]) for i, c in enumerate(cases))}]}}</script>
<style>body{{font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;margin:0 auto;padding:24px 18px;background:#0b0d12;color:#e8ecf4}}a{{color:#4f8cff}}code{{font-family:ui-monospace,monospace;font-size:13px}}table{{border-collapse:collapse;width:100%;margin:14px 0}}td,th{{border:1px solid #232838;padding:6px 8px;text-align:left}}.mut{{color:#9aa4b8}}</style>
</head><body>
<h1>Ten Base tokens, read at their block</h1>
<p>Chosen by 24h trading volume on Base — the tokens people are trading most, not the tokens that
asked for an audit. Each page shows who can mint, change or upgrade the contract at a named block,
plus a sha256 and a list of what was <em>not</em> checked.</p>
<p class="mut">Generated {html.escape(now.isoformat()[:19])}Z · selection source: GeckoTerminal
trending pools, Base. Volume is a proxy for attention, not for demand for this service.</p>
<table><tr><th>token</th><th>contract</th><th>verdict</th><th>block</th><th>flagged</th></tr>{rows}</table>
<p class="mut">None of these pages is a safety certification, and none of them tests whether a
token can be sold.</p>
<p><a href="../../audit/">← the audit service</a></p>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    if a.select:
        panel = select(candidates(_get(GECKO)))
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps({"schema": "af.e2.panel.v1", "selected_at": now.isoformat(),
                                      "source": GECKO, "tokens": panel},
                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("selected", len(panel), "tokens ->", LEDGER)
        for t in panel:
            print(" ", t["symbol"], t["address"], round(t["h24_volume_usd"]))
        return 0
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    cases = []
    for t in ledger["tokens"]:
        try:
            c = build(t, now=now)
        except Exception as e:
            print("skip", t["symbol"], type(e).__name__, e)
            continue
        cases.append(c)
        (OUT / (c["slug"] + ".html")).write_text(render(c), encoding="utf-8")
        print("%-10s block=%s verdict=%s" % (c["symbol"], c["block"], c["verdict"]))
        time.sleep(1)
    (OUT / "index.html").write_text(render_index(cases, now), encoding="utf-8")
    ledger.update({"schema": "af.e2.panel.v1", "built_at": now.isoformat(),
                   "cases": cases, "pages": len(cases)})
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", len(cases), "pages + index")
    return 0


if __name__ == "__main__":
    sys.exit(main())

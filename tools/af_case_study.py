#!/usr/bin/env python3
"""Three case studies that a buyer can check, built from the same engine the shop runs.

Each case shows a different verdict on purpose — a single-key owner, a renounced contract and
a contract owner — because a shop that only shows its best-looking result is a brochure, not
evidence. Every value carries the block it was read at; the free-scanner column carries what
the free scanner actually returned, so the comparison cannot be tilted.

Writes site/audit/cases/<slug>.json and site/audit/cases/index.html.

Usage:
  python3 tools/af_case_study.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_token_review as tr  # noqa: E402

OUT = Path("site/audit/cases")
GOPLUS = ("https://api.gopluslabs.io/api/v1/token_security/8453"
          "?contract_addresses={address}")
GOPLUS_FIELDS = ("is_honeypot", "buy_tax", "sell_tax", "holder_count", "owner_address",
                 "is_open_source", "is_mintable")

CASES = [
    {"slug": "single-key-owner", "address": "0x20116282bf477f796749567d283ef733d3ee5704",
     "why": "the owner is one wallet: every privileged action is one key away"},
    {"slug": "renounced", "address": "0x1252230193c0aaa10eb8b59a31ed8ec92e27a081",
     "why": "ownership renounced and not upgradeable: the strongest thing a contract can show"},
    {"slug": "contract-owner", "address": "0x089e1d9678569dbf2ee5c3bdff0699aee157d709",
     "why": "the owner is a contract, so the real question moves to who controls that contract"},
]


def goplus(address, tries=2):
    """What the free scanner says about the same address. None when it will not answer."""
    for i in range(tries):
        try:
            with urllib.request.urlopen(GOPLUS.format(address=address), timeout=15) as r:
                body = json.loads(r.read().decode())
            row = (body.get("result") or {}).get(address.lower()) or {}
            return {k: row.get(k) for k in GOPLUS_FIELDS if k in row} or None
        except Exception:
            if i:
                return None
            time.sleep(2)
    return None


def build(address, why, slug, now=None):
    now = now or datetime.now(timezone.utc)
    rep = tr.review("base", address)
    verdict = tr.verdict(rep)
    reads = rep.get("reads") or {}
    case = {
        "schema": "af.case_study.v1",
        "slug": slug,
        "at": now.isoformat(),
        "why": why,
        "chain": "base",
        "address": address,
        "symbol": reads.get("symbol"),
        "name": reads.get("name"),
        "block": rep.get("blockNumber"),
        "verdict": verdict,
        "facts": {k: reads.get(k) for k in ("symbol", "name", "decimals", "totalSupplyTokens",
                                            "owner", "bytecodeScannedAddress") if k in reads},
        "not_established": reads.get("notChecked") or [],
        "errors": rep.get("errors") or [],
        "free_scanner": goplus(address),
        "report": "site/reviews/base-%s.json" % address.lower(),
    }
    case["report_sha256"] = hashlib.sha256(
        json.dumps(rep, sort_keys=True).encode("utf-8")).hexdigest()
    return case


def cell(v, dash="not returned"):
    return dash if v is None else str(v)


def render(cases, now):
    items = {"@context": "https://schema.org", "@type": "ItemList",
             "name": "Base token audit case studies",
             "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                  "url": "https://farmmer938-lgtm.github.io/"
                                         f"autonomous-zero-baht/audit/cases/#{c['slug']}"}
                                 for i, c in enumerate(cases)]}
    items_json = json.dumps(items)
    rows = []
    for c in cases:
        f = c["free_scanner"] or {}
        rows.append(
            f"<h2 id=\"{c['slug']}\">{c['symbol'] or c['address'][:10]} — {c['verdict']}</h2>"
            f"<p class=mut>Why this case is here: {c['why']}</p>"
            "<table><tr><th>What</th><th>This report (chain)</th>"
            "<th>Free scanner (quoted)</th></tr>"
            f"<tr><td>address</td><td><code>{c['address']}</code></td>"
            f"<td><code>{cell(f.get('owner_address'))}</code></td></tr>"
            f"<tr><td>owner</td><td><code>{cell(c['facts'].get('owner'), 'no owner() surface')}</code></td>"
            f"<td>—</td></tr>"
            f"<tr><td>total supply</td><td>{cell(c['facts'].get('totalSupplyTokens'))}</td>"
            f"<td>—</td></tr>"
            f"<tr><td>read at block</td><td><strong>{c['block']}</strong></td><td>—</td></tr>"
            f"<tr><td>is_mintable</td><td>see verdict</td><td>{cell(f.get('is_mintable'))}</td></tr>"
            f"<tr><td>buy / sell tax</td><td>not read (needs a live swap)</td>"
            f"<td>{cell(f.get('buy_tax'))} / {cell(f.get('sell_tax'))}</td></tr>"
            f"<tr><td>honeypot</td><td>not read (needs a live swap)</td>"
            f"<td>{cell(f.get('is_honeypot'))}</td></tr>"
            f"<tr><td>holder count</td><td>not read</td>"
            f"<td>{cell(f.get('holder_count'))}</td></tr>"
            f"<tr><td>report sha256</td><td><code>{c['report_sha256'][:24]}…</code></td>"
            f"<td>no reproducible hash</td></tr></table>"
            "<p class=mut><strong>What this case does not establish:</strong> "
            + "; ".join(c["not_established"] or ["nothing was flagged as unreadable"])
            + f". <a href=\"../../reviews/base-{c['address'].lower()}.json\">full JSON</a></p>")
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Three Base token audits, three different verdicts | AF</title>
<meta name="description" content="Three real Base-token audits shown side by side with what a free scanner returned for the same address: single-key owner, renounced contract, and a contract owner. Every value carries its block number and a reproducible hash.">
<link rel="canonical" href="https://farmmer938-lgtm.github.io/autonomous-zero-baht/audit/cases/">
<script type="application/ld+json">
{items_json}
</script>
<style>
 body{{margin:0;background:#0b0d12;color:#e8ecf4;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.65}}
 .wrap{{max-width:900px;margin:0 auto;padding:0 20px}}
 header{{padding:46px 0 22px;border-bottom:1px solid #232838}}
 h1{{font-size:30px;margin:0 0 8px}} h2{{font-size:20px;margin:30px 0 6px}}
 table{{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0}}
 th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid #232838;vertical-align:top}}
 th{{color:#9aa4b8;font-size:13px}} code{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}}
 .mut{{color:#9aa4b8;font-size:14px}} a{{color:#4f8cff}}
 footer{{margin:40px 0 60px;color:#9aa4b8;font-size:13px;border-top:1px solid #232838;padding-top:14px}}
</style></head>
<body><header><div class="wrap">
<h1>Three audits, three different verdicts</h1>
<p class="mut">Generated {now.isoformat(timespec='minutes')} by the same engine that answers
orders. Each row on the left was read from the chain at the quoted block; each row on the
right is what a free scanner returned for the same address at the time of generation. Where
we do not read a field, it says so instead of copying the scanner's answer.</p>
<p class="mut"><a href="../">Order an audit</a> · <a href="../../reviews.html">all 227 reports</a>
· <a href="../guides/check-a-base-token.html">how to check a token yourself</a></p>
</div></header><div class="wrap">
{''.join(rows)}
<footer>
<p><strong>This is not a safety certification.</strong> A verdict describes the control
surface that could be read at one block. Contracts can change, and the fields marked "not
read" are exactly the ones a buyer most wants — which is why they are labelled, not guessed.</p>
<p>Prices are an offer, not a claim of sales. This page was written by an AI agent
(OpenHands) on behalf of K.</p>
</footer></div></body></html>
"""
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    now = datetime.now(timezone.utc)
    cases = []
    for c in CASES:
        try:
            case = build(c["address"], c["why"], c["slug"], now)
        except Exception as e:
            print(f"{c['slug']}: FAILED {type(e).__name__}: {e}")
            continue
        cases.append(case)
        print(f"{c['slug']}: {case['verdict']} block={case['block']} "
              f"goplus={'yes' if case['free_scanner'] else 'no answer'}")
    if not cases:
        print("no case could be built; nothing written")
        return 1
    html = render(cases, now)
    if a.write:
        OUT.mkdir(parents=True, exist_ok=True)
        for case in cases:
            (OUT / f"{case['slug']}.json").write_text(
                json.dumps(case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        (OUT / "index.html").write_text(html, encoding="utf-8")
        print("wrote", OUT / "index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())

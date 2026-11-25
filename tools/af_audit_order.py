#!/usr/bin/env python3
"""Turn an `audit-request` issue into a delivered report, without a server.

The shop front promises "open an issue, get the report in the issue". This is the part that
keeps that promise: it parses the issue form, validates the two fields it trusts, runs the
same engine behind the 227 public reports, and writes the reply plus an order record.

The issue body is untrusted text from a stranger, so it is never executed: an address is
matched against `^0x[0-9a-fA-F]{40}$` and a chain against a whitelist, and nothing else in
the body is used. The reply never claims a payment; only the ledger does that.

Usage:
  python3 tools/af_audit_order.py --issue 42 --body-file body.md --comment-out c.md --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_selfserve as ss  # noqa: E402
import af_token_review as tr  # noqa: E402

CHAINS = {"base": 8453}
PRICE_USDC = ss.MICRO_TIER["usdc"]
PAY_TO = ss.AF
ORDERS = Path("site/api/orders")
REVIEWS = Path("site/reviews")
SECTION = re.compile(r"^###\s+(.+?)\s*\n+(.*?)(?=^###\s|\Z)", re.S | re.M)
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
FIELD_LABELS = {"chain": "chain", "token contract address": "address",
                "what do you need to know?": "question", "payment": "payment_intent"}


def parse_issue(body):
    """Form-rendered issue body -> {chain, address, question, payment_intent}."""
    fields = {}
    for label, value in SECTION.findall(body or ""):
        key = FIELD_LABELS.get(label.strip().lower())
        if key:
            fields[key] = value.strip()
    return fields


def validate(fields):
    """(ok, reason). Only base is supported today, and only a bare 0x address."""
    chain = (fields.get("chain") or "").strip().lower()
    address = (fields.get("address") or "").strip()
    if chain not in CHAINS:
        return False, f"chain {chain!r} is not supported; supported: {', '.join(CHAINS)}"
    if not ADDRESS.match(address):
        return False, "the address is not a 40-hex 0x address"
    return True, "ok"


def report_path(chain, address):
    return REVIEWS / f"{chain}-{address.lower()}.json"


def digest(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def render_comment(order):
    """The reply. It quotes the report and never says the order is paid."""
    lines = [f"## Audit: `{order['address']}` on {order['chain']}", ""]
    if order["status"] == "failed":
        lines += [f"**The report could not be produced.** {order['error']}", "",
                  "Nothing is owed for this. Re-open the issue with a fixed address and AF "
                  "will try again."]
        return "\n".join(lines)
    rep = order["report"]
    reads = rep.get("reads") or {}
    lines += ["| field | value |", "|---|---|"]
    for label, key in (("symbol", "symbol"), ("decimals", "decimals"),
                       ("total supply", "totalSupplyTokens"), ("owner", "owner")):
        if key in reads:
            lines.append(f"| {label} | `{reads[key]}` |")
    if rep.get("blockNumber"):
        lines.append(f"| block | `{rep['blockNumber']}` |")
    lines += ["", f"**Verdict:** {order['verdict']}", ""]
    missing = reads.get("notChecked") or []
    if missing:
        lines += ["**What this report does not establish**", ""]
        lines += [f"- {m}" for m in missing] + [""]
    lines += ["Full JSON (diffable across runs): "
              f"[`{order['report_path']}`](https://farmmer938-lgtm.github.io/"
              f"autonomous-zero-baht/reviews/{order['report_path'].split('/')[-1]})", "",
              f"Report sha256: `{order['report_sha256']}`", "",
              "---", "",
              f"Price for this audit is **{PRICE_USDC:.2f} USDC** on Base to "
              f"`{PAY_TO}`. The amount is the order reference. This order is **not** marked "
              f"paid until a confirmed on-chain payment is matched; nothing in this comment "
              f"is a payment claim.", "",
              "This comment was written by an AI agent (OpenHands) on behalf of K."]
    return "\n".join(lines)


def build_order(issue_number, body, now=None):
    now = now or datetime.now(timezone.utc)
    fields = parse_issue(body)
    order = {
        "schema": "af.audit_order.v1",
        "issue": int(issue_number),
        "at": now.isoformat(),
        "chain": (fields.get("chain") or "").strip().lower(),
        "address": (fields.get("address") or "").strip(),
        "question": fields.get("question"),
        "payment_intent": fields.get("payment_intent"),
        "price_usdc": PRICE_USDC,
        "pay_to": PAY_TO,
        "payment_tx": None,
        "paid": False,
    }
    ok, reason = validate(fields)
    if not ok:
        return {**order, "status": "failed", "error": reason}
    try:
        rep = tr.review(order["chain"], order["address"])
        verdict = tr.verdict(rep)
    except Exception as e:  # an RPC hiccup is a failure to deliver, not a sale
        return {**order, "status": "failed", "error": f"engine error: {type(e).__name__}: {e}"}
    path = report_path(order["chain"], order["address"])
    return {**order, "status": "delivered_unpaid", "verdict": verdict, "report": rep,
            "report_path": str(path),
            "report_sha256": digest(json.dumps(rep, sort_keys=True))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True, type=int)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--comment-out", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    body = Path(a.body_file).read_text(encoding="utf-8")
    order = build_order(a.issue, body)
    comment = render_comment(order)
    Path(a.comment_out).write_text(comment, encoding="utf-8")
    if a.write:
        ORDERS.mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in order.items() if k != "report"}
        Path(ORDERS, f"{a.issue}.json").write_text(
            json.dumps(public, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if order["status"] != "failed":
            REVIEWS.mkdir(parents=True, exist_ok=True)
            Path(order["report_path"]).write_text(
                json.dumps(order["report"], ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")
    print(f"issue {a.issue}: {order['status']}"
          + (f" ({order['error']})" if order.get("error") else f" verdict={order['verdict']}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

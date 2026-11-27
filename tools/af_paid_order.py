#!/usr/bin/env python3
"""Deliver a paid order from a GitHub issue, with no server.

The x402 cashier runs on a host that dies with the sandbox, so a buyer who arrives between a
pod recycle and the next boot has nowhere to pay. This is the durable rail: the buyer transfers
USDC on Base from their own wallet and opens an issue carrying the tx hash. The payment is read
from the chain, never from the issue text, and delivery happens in the issue itself.

The issue body is untrusted: only a 0x tx hash and a 0x token address are extracted, both by
regex, and nothing in the body is executed.

Usage:
  python3 tools/af_paid_order.py --issue 42 --body-file body.md \
      --labels paid-order --comment-out c.md --write
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import af_selfserve as ss  # noqa: E402
import af_token_review as tr  # noqa: E402

CHECK_USDC = 0.05   # address read + verdict
REPORT_USDC = 0.50  # the same, pinned, plus the full JSON report
ORDERS = Path("site/api/orders")
REVIEWS = Path("site/reviews")
SECTION = re.compile(r"^###\s+(.+?)\s*\n+(.*?)(?=^###\s|\Z)", re.S | re.M)
TX = re.compile(r"0x[0-9a-fA-F]{64}")
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
FIELD_LABELS = {"base usdc transaction hash": "tx", "token contract address (base)": "address",
                "what do you need to know?": "question"}


def parse_issue(body: str) -> dict:
    fields = {}
    for label, value in SECTION.findall(body or ""):
        key = FIELD_LABELS.get(label.strip().lower())
        if key:
            fields[key] = value.strip()
    return fields


def _transfer_amount(log: dict) -> float:
    return int(log.get("data") or "0x0", 16) / 1e6


def verify(tx_hash: str, pay_to: str = ss.AF) -> dict:
    """Read one Base tx and decide whether it paid `pay_to`. Never guesses."""
    try:
        receipt = ss.rpc("eth_getTransactionReceipt", [tx_hash])
        latest = int(ss.rpc("eth_blockNumber", []), 16)
    except Exception as e:  # an RPC failure is "unverified", never "unpaid"
        return {"status": "unverified", "reason": f"rpc error: {type(e).__name__}: {e}"}
    if not receipt:
        return {"status": "not_found", "reason": "no receipt for this hash on Base (pending or wrong chain)"}
    if int(receipt.get("status") or "0x0", 16) != 1:
        return {"status": "reverted", "reason": "the transaction reverted"}
    to_topic = "0x" + "0" * 24 + pay_to[2:].lower()
    paid, payer = 0.0, None
    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if (log.get("address", "").lower() != ss.USDC_BASE.lower() or len(topics) < 3
                or topics[0].lower() != ss.TRANSFER or topics[2].lower() != to_topic):
            continue
        paid += _transfer_amount(log)
        payer = payer or "0x" + topics[1][-40:]
    if paid <= 0:
        return {"status": "no_transfer",
                "reason": f"no USDC transfer to {pay_to} inside this transaction"}
    block = int(receipt["blockNumber"], 16)
    depth = latest - block
    out = {"status": "paid" if depth >= ss.MIN_CONFIRMATIONS else "pending",
           "amount_usdc": round(paid, 6), "payer": payer, "block": block,
           "confirmations": depth, "tx": tx_hash}
    if depth < ss.MIN_CONFIRMATIONS:
        out["reason"] = f"{depth} confirmation(s), needs {ss.MIN_CONFIRMATIONS}"
    return out


def tier_for(amount: float) -> str | None:
    if amount >= REPORT_USDC:
        return "report"
    if amount >= CHECK_USDC:
        return "check"
    return None


def build_order(issue: int, body: str, labels=(), now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    fields = parse_issue(body)
    tx_match = TX.search(fields.get("tx") or "")
    addr_match = ADDRESS.search(fields.get("address") or "")
    order = {
        "schema": "af.paid_order.v1",
        "issue": int(issue),
        "at": now.isoformat(),
        "tx": tx_match.group(0) if tx_match else None,
        "address": addr_match.group(0) if addr_match else None,
        "question": fields.get("question"),
        "pay_to": ss.AF,
        "paid": False,
        "amount_usdc": 0.0,
        "tier": None,
        "payer": None,
        "self_test": "self-test" in {l.strip().lower() for l in (labels or [])},
    }
    if not order["tx"]:
        return {**order, "status": "unverified", "reason": "no 0x transaction hash in the issue"}
    pay = verify(order["tx"])
    order.update({"payment": pay, "amount_usdc": pay.get("amount_usdc", 0.0),
                  "payer": pay.get("payer")})
    if pay["status"] != "paid":
        return {**order, "status": "unverified", "reason": pay.get("reason") or pay["status"]}
    tier = tier_for(pay["amount_usdc"])
    if not tier:
        return {**order, "status": "underpaid",
                "reason": f"{pay['amount_usdc']} USDC is below the {CHECK_USDC:.2f} USDC minimum"}
    order["paid"] = True
    order["tier"] = tier
    order["customer"] = (pay.get("payer") or "").lower() not in ss.SELF_SENDERS
    if not order["address"]:
        return {**order, "status": "paid_no_payload",
                "reason": "payment verified but the issue carries no token address to report on"}
    try:
        rep = tr.review("base", order["address"])
        verdict = tr.verdict(rep)
    except Exception as e:
        return {**order, "status": "paid_delivery_failed", "reason": f"engine error: {type(e).__name__}: {e}"}
    return {**order, "status": "delivered_paid", "verdict": verdict, "report": rep}


def render_comment(order: dict) -> str:
    head = f"## Order `{order['tx'] or 'no tx'}`"
    lines = [head, ""]
    st = order["status"]
    if st == "delivered_paid":
        p = order["payment"]
        lines += [f"**Payment verified on chain.** {p['amount_usdc']} USDC to `{ss.AF}` on Base, "
                  f"payer `{p['payer']}`, block `{p['block']}`, {p['confirmations']} confirmations.",
                  f"Tier bought: **{order['tier']}**.", ""]
    elif st == "paid_no_payload":
        lines += [f"**Payment verified on chain** ({order['amount_usdc']} USDC). "
                  f"Nothing to report yet: {order['reason']}. Reply with the address and AF "
                  "will deliver in this issue; the payment is already recorded.", ""]
    elif st == "paid_delivery_failed":
        lines += [f"**Payment verified on chain** ({order['amount_usdc']} USDC) but delivery failed: "
                  f"{order['reason']}. The payment stands; re-run the workflow from the Actions tab "
                  "and the report will be produced.", ""]
    elif st == "underpaid":
        lines += [f"**Payment found but below the minimum.** {order['reason']}. "
                  f"Nothing is owed for the shortfall; send the difference to `{ss.AF}` on Base "
                  "and add that tx hash to this issue.", ""]
    else:
        lines += [f"**Not verified: {order['reason']}.** Nothing in this reply is a payment claim. "
                  f"The check reads the chain, so a hash that is pending, reverted, on another "
                  f"chain, or that never sent USDC to `{ss.AF}` reads as unpaid.", ""]

    if order.get("report"):
        rep = order["report"]
        reads = rep.get("reads") or {}
        lines += [f"### Report: `{order['address']}` on Base", "", "| field | value |", "|---|---|"]
        for label, key in (("symbol", "symbol"), ("decimals", "decimals"),
                           ("total supply", "totalSupplyTokens"), ("owner", "owner")):
            if key in reads:
                lines.append(f"| {label} | `{reads[key]}` |")
        if rep.get("blockNumber"):
            lines.append(f"| block | `{rep['blockNumber']}` |")
        lines += ["", f"**Verdict:** {order['verdict']}", ""]
        missing = reads.get("notChecked") or []
        if missing:
            lines += ["**What this report does not establish**", ""] + [f"- {m}" for m in missing] + [""]

    lines += ["---", "",
              f"Prices: **{CHECK_USDC:.2f} USDC** for the read + verdict, **{REPORT_USDC:.2f} USDC** "
              f"to have it pinned. Pay on Base to `{ss.AF}` from any wallet, then open this form "
              "with the tx hash. No account, no signup, no server.",
              "", "This comment was written by an AI agent (OpenHands) on behalf of K."]
    return "\n".join(lines)


def _ledger_append(order: dict) -> None:
    path = Path(ss.LEDGER)
    ledger = ss.load_paid()
    if any(p.get("txHash", "").lower() == (order["tx"] or "").lower() for p in ledger["payments"]):
        return
    ledger["payments"].append({
        "txHash": order["tx"], "block": order["payment"]["block"],
        "from": order["payment"]["payer"], "amount_usdc": order["amount_usdc"],
        "at": datetime.now(timezone.utc).isoformat(), "confirmed": True,
        "tier": order["tier"], "issue": order["issue"], "customer": order.get("customer", False),
        "evidence": f"base tx {order['tx']} in block {order['payment']['block']}",
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", required=True, type=int)
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--labels", default="")
    ap.add_argument("--comment-out", required=True)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    body = Path(a.body_file).read_text(encoding="utf-8")
    labels = [l for l in a.labels.split(",") if l.strip()]
    order = build_order(a.issue, body, labels=labels)
    Path(a.comment_out).write_text(render_comment(order), encoding="utf-8")
    if a.write:
        ORDERS.mkdir(parents=True, exist_ok=True)
        public = {k: v for k, v in order.items() if k != "report"}
        Path(ORDERS, f"paid-{a.issue}.json").write_text(
            json.dumps(public, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if order["status"] == "delivered_paid":
            REVIEWS.mkdir(parents=True, exist_ok=True)
            Path(REVIEWS, f"base-{order['address'].lower()}.json").write_text(
                json.dumps(order["report"], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        if order["paid"]:
            _ledger_append(order)
    print(f"issue {a.issue}: {order['status']} tier={order['tier']} "
          f"amount={order['amount_usdc']}" + (f" ({order.get('reason')})" if order.get("reason") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

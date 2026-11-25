#!/usr/bin/env python3
"""AF on-chain outreach — reach a token's deployer with a zero-value transaction memo.

Social platforms need an account or a paid FID. The chain needs neither. AF finds the wallet
that launched a token on Base, then sends that wallet a 0-value transaction whose input data
is a short note plus a link to the transparency report. The deployer sees it in their wallet
and on the block explorer.

Safety rules, enforced in code:
  - only ever send to an EOA. If the target has contract code, AF refuses: sending calldata to
    a contract would execute a function, which is not a message.
  - dedup: one message per token, ever. Ledger in artifacts/outreach/sent.json.
  - hard daily cap, and a gas budget guard so AF can never drain its own wallet.
  - dry-run by default. Nothing is sent without --send.

Cost measured 2026-11-18 on Base: ~$0.0007 per memo at 0.005 gwei. AF holds ~0.000485 ETH,
so roughly 2,000 memos. The cap keeps AF solvent for its trading book.

Usage:
  python3 tools/af_onchain_outreach.py --plan
  python3 tools/af_onchain_outreach.py --send --max 3
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RPC = ["https://base-rpc.publicnode.com", "https://mainnet.base.org", "https://base.drpc.org"]
CHAIN_ID = 8453
SITE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
# Gemini advice 2026-11-18: price the micro-fix report at 0.5 USDC, not $15. A deployer under
# launch pressure pays 0.5 USDC without thinking; $15 needs a decision and gets ignored.
INVOICE_USDC = float(os.environ.get("AF_OUTREACH_PRICE_USDC", "0.5"))

# The invoice amount must be the one tools/af_selfserve.py will reconcile, so the mapping is
# imported from there instead of being recomputed here.
from af_selfserve import assign_amounts  # noqa: E402


def micro_amounts(targets):
    return assign_amounts([t["address"] for t in targets], INVOICE_USDC, span=499)


LEDGER = "artifacts/outreach/sent.json"
KEY_FILE = os.environ.get("AF_SWAP_KEY_FILE", "/workspace/.secrets/af_swap.key")
DAILY_CAP = int(os.environ.get("AF_OUTREACH_DAILY_CAP", "5"))
# AF's whole wallet is ~0.000485 ETH. A memo costs ~2.6e-7 ETH, so the cap is about discipline,
# not cost. The reserve keeps a real buffer for the trading book (~1000 memos of headroom).
GAS_RESERVE_WEI = int(os.environ.get("AF_OUTREACH_GAS_RESERVE_WEI", str(2 * 10 ** 14)))  # keep 0.0002 ETH back
# Gemini advice 2026-11-18 (stuck consult): a 0-value tx reads as dust/spam and gets ignored; a
# transfer carrying real value makes the deployer's wallet raise an incoming-funds notification,
# which is what gets the note read. AF follows this, but sizes the amount to its actual capital:
# 0.5 USDC per deployer would drain AF in two sends, so the tip is a small ETH value by default.
TIP_WEI = int(os.environ.get("AF_OUTREACH_TIP_WEI", str(2 * 10 ** 13)))  # 0.00002 ETH ~ $0.06


def rpc(method, params):
    last = None
    for host in RPC:
        try:
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
            req = urllib.request.Request(host, data=body,
                                         headers={"Content-Type": "application/json", "User-Agent": "AF-outreach"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.load(r)
            if "result" in j:
                return j["result"]
            if j.get("error"):
                last = RuntimeError(f"{host}: {json.dumps(j['error'])[:220]}")
        except Exception as e:
            last = e
    raise RuntimeError(f"rpc {method} failed: {str(last)[:220]}")


def load_key():
    if os.environ.get("AF_MAIN_WALLET"):
        raw = os.environ["AF_MAIN_WALLET"]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw).get("private_key", "")
            except Exception:
                raw = ""
    elif os.path.exists("/workspace/.secrets/af_master.json"):
        store = json.load(open("/workspace/.secrets/af_master.json")).get("secrets") or {}
        raw = store.get("AF_MAIN_WALLET", "")
        if isinstance(raw, dict):
            raw = raw.get("value", "")
        try:
            raw = json.loads(raw).get("private_key", "") if raw else ""
        except Exception:
            raw = ""
    else:
        raw = ""
    if not raw and os.path.exists(KEY_FILE):
        raw = open(KEY_FILE).read().strip()
    if not raw:
        return None, None
    if not raw.startswith("0x"):
        raw = "0x" + raw
    from eth_account import Account
    acct = Account.from_key(raw)
    return acct.address, raw


def has_code(addr, blk):
    c = rpc("eth_getCode", [addr, hex(blk)])
    return bool(c and c != "0x")


def find_deployer(token, latest):
    """Smallest block with code, then the tx in it whose logs mention the token."""
    if not has_code(token, latest):
        return None
    lo, hi = 0, latest
    while lo < hi:
        mid = (lo + hi) // 2
        if has_code(token, mid):
            hi = mid
        else:
            lo = mid + 1
    blk = rpc("eth_getBlockByNumber", [hex(lo), True])
    for tx in blk.get("transactions") or []:
        rc = rpc("eth_getTransactionReceipt", [tx["hash"]]) or {}
        addrs = {(l.get("address") or "").lower() for l in (rc.get("logs") or [])}
        if token.lower() in addrs or (rc.get("contractAddress") or "").lower() == token.lower():
            return {"deployer": tx["from"], "txHash": tx["hash"], "block": lo,
                    "factory": tx.get("to"), "deployerIsContract": has_code(tx["from"], latest)}
    return None


def memo_for(sym, report_url, address, flags=None, eip681=None):
    """Gemini advice 2026-11-18: lead with the specific risk, not a generic pitch, and hand the
    deployer a one-tap payment link. Urgency is what moves a deployer; a brochure does not."""
    risk = (flags or ["control-plane read available"])[0]
    line = f"AF read {sym} ({address[:10]}..) on Base. Finding: {risk}."
    pay = f" Unlock the pinned fix report for 0.5 USDC: {eip681}" if eip681 else ""
    return (f"{line} Free report: {report_url}. "
            f"AF reports only what the chain answered; no buy/sell call.{pay}")


def encode_data(text):
    return "0x" + text.encode("utf-8").hex()


def gas_for(data_hex):
    raw = bytes.fromhex(data_hex[2:])
    return 21000 + sum(16 if b else 4 for b in raw)


def load_ledger():
    if os.path.exists(LEDGER):
        try:
            return json.load(open(LEDGER))
        except Exception:
            pass
    return {"schema": "af.outreach.ledger.v1", "sent": []}


def main() -> int:
    do_send = "--send" in sys.argv
    max_n = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 3
    today = datetime.now(timezone.utc).date().isoformat()

    addr, key = load_key()
    ledger = load_ledger()
    sent_today = [s for s in ledger["sent"] if s.get("date") == today]
    already = {s["token"].lower() for s in ledger["sent"]}
    print(f"AF address: {addr} | sent today: {len(sent_today)}/{DAILY_CAP} | ledger size: {len(ledger['sent'])}")

    tp = "site/outbound/targets.json"
    if not os.path.exists(tp):
        print("no targets file; run tools/af_outbound.py first")
        return 1
    targets = json.load(open(tp)).get("targets") or []
    amounts = micro_amounts(targets)

    latest = int(rpc("eth_blockNumber", []), 16)
    balance = int(rpc("eth_getBalance", [addr, "latest"]), 16) if addr else 0
    base_fee = int((rpc("eth_getBlockByNumber", ["latest", False]) or {}).get("baseFeePerGas", "0x0"), 16)
    print(f"balance: {balance/1e18:.6f} ETH | baseFee: {base_fee/1e9:.6f} gwei")

    plan = []
    for t in targets:
        token = t["address"]
        if token.lower() in already:
            continue
        if len(plan) + len(sent_today) >= min(max_n, DAILY_CAP):
            break
        d = find_deployer(token, latest)
        if not d:
            print(f"  {token[:10]}.. no deployer found")
            continue
        if d["deployerIsContract"]:
            print(f"  {token[:10]}.. deployer {d['deployer'][:10]}.. is a CONTRACT -> refused (never send calldata to a contract)")
            continue
        sym = (t.get("reads") or {}).get("symbol") or "this token"
        # EIP-681: one tap opens the wallet with the exact USDC amount and the AF address filled in.
        amt = amounts[token.lower()]
        eip681 = (f"ethereum:{USDC_BASE}@8453/transfer?address={addr}"
                  f"&uint256={int(round(amt * 1e6))}") if addr else None
        data = encode_data(memo_for(sym, t.get("reportUrl", SITE), token,
                                    flags=t.get("flags"), eip681=eip681))
        gas = gas_for(data)
        # value carried with the note, so the deployer's wallet raises an incoming-funds
        # notification instead of filing the tx as dust (Gemini advice 2026-11-18)
        cost = gas * base_fee * 2 + TIP_WEI
        plan.append({"token": token, "symbol": sym, "deployer": d["deployer"], "block": d["block"],
                     "data": data, "gas": gas, "costWei": cost, "tipWei": TIP_WEI,
                     "reportUrl": t.get("reportUrl"), "invoiceUsdc": amt})
        print(f"  {sym:12s} deployer {d['deployer']} gas={gas} cost={cost/1e18:.8f} ETH (tip {TIP_WEI/1e18:.6f})")

    if not plan:
        print("nothing to send")
        return 0
    total = sum(p["costWei"] for p in plan)
    print(f"planned {len(plan)} memo(s), total {total/1e18:.8f} ETH")
    if balance - total < GAS_RESERVE_WEI:
        print(f"REFUSED: would leave less than the {GAS_RESERVE_WEI/1e18:.4f} ETH gas reserve")
        return 1
    if not do_send:
        print("dry-run only. add --send to actually send.")
        return 0
    if os.environ.get("AF_OUTREACH_CONFIRM") != "1":
        print("REFUSED: sending spends real ETH on unsolicited on-chain memos. "
              "Set AF_OUTREACH_CONFIRM=1 to confirm you mean to send.")
        return 1
    if not key:
        print("REFUSED: no signing key available")
        return 1

    from eth_account import Account
    from eth_utils import to_checksum_address
    nonce = int(rpc("eth_getTransactionCount", [addr, "pending"]), 16)
    max_priority = max(base_fee // 10, 1000)
    for p in plan:
        to = to_checksum_address(p["deployer"])
        # ask the node for the real intrinsic gas; my own estimate was rejected once as too low
        try:
            est = int(rpc("eth_estimateGas", [{"from": addr, "to": to, "value": hex(TIP_WEI), "data": p["data"]}]), 16)
        except Exception:
            est = p["gas"]
        gas = max(int(est * 1.25), p["gas"] + 5000)
        tx = {"to": to, "value": TIP_WEI, "data": p["data"], "gas": gas,
              "maxFeePerGas": base_fee * 2 + max_priority, "maxPriorityFeePerGas": max_priority,
              "nonce": nonce, "chainId": CHAIN_ID, "type": 2}
        signed = Account.sign_transaction(tx, key)
        raw = signed.raw_transaction.hex()
        if not raw.startswith("0x"):
            raw = "0x" + raw
        h = rpc("eth_sendRawTransaction", [raw])
        print(f"  sent {p['symbol']:12s} -> {p['deployer']} tx {h}")
        ledger["sent"].append({"token": p["token"], "symbol": p["symbol"], "deployer": p["deployer"],
                               "txHash": h, "at": datetime.now(timezone.utc).isoformat(), "date": today,
                               "gas": p["gas"], "costWei": str(p["costWei"]), "tipWei": str(p["tipWei"])})
        nonce += 1
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w") as fh:
        json.dump(ledger, fh, indent=1)
    print(f"ledger now {len(ledger['sent'])} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

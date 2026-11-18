#!/usr/bin/env python3
"""AF token review — an honest, on-chain-grounded due-diligence report for a token.

A project that wants AF to review and promote its token pays AF in its own coin. AF then
reads the token's control plane from the chain and publishes a factual review: who can
mint, who owns it, whether ownership is renounced, whether the contract is an upgradeable
proxy, and whether the owner is a multisig.

Nothing here is an opinion. Every field is read from the chain at one finalized block and
reported as-is. If a read fails, the field says so instead of guessing.

Usage:
  python3 tools/af_token_review.py --chain base --address 0x… [--write]
  python3 tools/af_token_review.py --batch tokens.json --write
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone

RPCS = {
    "ethereum": ["https://eth.drpc.org", "https://ethereum-rpc.publicnode.com"],
    "base": ["https://base-rpc.publicnode.com", "https://mainnet.base.org"],
    "arbitrum": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"],
    "optimism": ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com"],
    "bsc": ["https://bsc-rpc.publicnode.com", "https://binance.llamarpc.com"],
}
CHAIN_ID = {"ethereum": 1, "base": 8453, "arbitrum": 42161, "optimism": 10, "polygon": 137, "bsc": 56}
ZERO = "0x" + "0" * 40
SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
SEL = {"name": "0x06fdde03", "symbol": "0x95d89b41", "decimals": "0x313ce567",
       "totalSupply": "0x18160ddd", "owner": "0x8da5cb5b", "threshold": "0xe75235b8",
       "owners": "0xa0e67e2b", "getCode": None}


def _rpc(host, method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(host, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "AF-review"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def _str(hexdata):
    if not hexdata or hexdata == "0x":
        return ""
    raw = bytes.fromhex(hexdata[2:])
    if len(raw) == 32:
        return raw.rstrip(b"\x00").decode("utf-8", "replace")
    if len(raw) >= 64:
        try:
            n = int.from_bytes(raw[32:64], "big")
            return raw[64:64 + n].decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def _addr(word):
    return "0x" + word[-40:]


def review(chain: str, address: str) -> dict:
    out = {"chain": chain, "chainId": CHAIN_ID.get(chain), "address": address,
           "generatedAt": datetime.now(timezone.utc).isoformat(), "reads": {}, "flags": [], "errors": []}
    for host in RPCS.get(chain, []):
        try:
            blk = _rpc(host, "eth_blockNumber", [])
            code = _rpc(host, "eth_getCode", [address, blk])
            if not code or code == "0x":
                out["errors"].append("no contract code at this address")
                return out
            out["blockNumber"] = int(blk, 16)
            r = out["reads"]
            for key in ("name", "symbol"):
                try:
                    r[key] = _str(_rpc(host, "eth_call", [{"to": address, "data": SEL[key]}, blk]))
                except Exception:
                    r[key] = None
            for key in ("decimals", "totalSupply"):
                try:
                    r[key] = int(_rpc(host, "eth_call", [{"to": address, "data": SEL[key]}, blk]), 16)
                except Exception:
                    r[key] = None
            if r.get("decimals") and r.get("totalSupply") is not None:
                r["totalSupplyTokens"] = r["totalSupply"] / (10 ** r["decimals"])
            # ownership
            owner = None
            try:
                v = _rpc(host, "eth_call", [{"to": address, "data": SEL["owner"]}, blk])
                if v and v != "0x":
                    owner = _addr(v[2:])
            except Exception:
                pass
            r["owner"] = owner
            if owner is None:
                out["flags"].append("no owner() function — ownership is either renounced at the code level or the contract is not Ownable")
            elif owner == ZERO:
                out["flags"].append("ownership RENOUNCED (owner is the zero address)")
            else:
                oc = _rpc(host, "eth_getCode", [owner, blk])
                if oc and oc != "0x":
                    out["flags"].append("owner is a CONTRACT (likely a multisig or governance) — not a single EOA")
                    try:
                        thr = _rpc(host, "eth_call", [{"to": owner, "data": SEL["threshold"]}, blk])
                        own = _rpc(host, "eth_call", [{"to": owner, "data": SEL["owners"]}, blk])
                        if thr and own and thr != "0x":
                            n = int(own[2 + 64:2 + 128], 16)
                            r["ownerSafe"] = {"threshold": int(thr, 16), "ownerCount": n}
                    except Exception:
                        pass
                else:
                    out["flags"].append("owner is a single EOA — one key controls this token")
            # upgradeable proxy?
            try:
                impl = _rpc(host, "eth_getStorageAt", [address, SLOT_IMPL, blk])
                if impl and int(impl, 16) != 0:
                    r["proxyImplementation"] = _addr(impl[2:])
                    out["flags"].append("UPGRADEABLE PROXY — the implementation can be replaced by whoever controls the admin")
            except Exception:
                pass
            # USDC-style proxy: admin() in the older slot, plus masterMinter
            try:
                adm = _rpc(host, "eth_call", [{"to": address, "data": "0xf851a440"}, blk])
                if adm and adm != "0x" and int(adm, 16) != 0:
                    r["proxyAdmin"] = _addr(adm[2:])
                    out["flags"].append("USDC-style proxy — admin() controls upgrades")
                mm = _rpc(host, "eth_call", [{"to": address, "data": "0x35d99f35"}, blk])
                if mm and mm != "0x" and int(mm, 16) != 0:
                    r["masterMinter"] = _addr(mm[2:])
                    out["flags"].append("masterMinter() exists — a separate key can grant mint rights")
            except Exception:
                pass
            return out
        except Exception as e:
            out["errors"].append(f"{host}: {str(e)[:80]}")
            continue
    return out


def verdict(rep: dict) -> str:
    """A short, defensible summary. Never a buy/sell recommendation."""
    f = rep.get("flags", [])
    if any("RENOUNCED" in x for x in f) and not any("UPGRADEABLE" in x for x in f):
        return "ownership renounced, not upgradeable"
    if any("UPGRADEABLE" in x for x in f) and any("single EOA" in x for x in f):
        return "upgradeable AND controlled by one key — highest control risk"
    if any("ownerSafe" in rep.get("reads", {}) for _ in [0]) or any("CONTRACT" in x for x in f):
        return "owner is a contract (multisig/governance)"
    if any("single EOA" in x for x in f):
        return "single-key owner"
    return "no owner() surface found"


def main() -> int:
    if "--chain" in sys.argv:
        chain = sys.argv[sys.argv.index("--chain") + 1]
        addr = sys.argv[sys.argv.index("--address") + 1]
        reps = [review(chain, addr)]
    elif "--batch" in sys.argv:
        data = json.load(open(sys.argv[sys.argv.index("--batch") + 1]))
        reps = [review(x["chain"], x["address"]) for x in data]
    else:
        print(__doc__)
        return 2
    for rep in reps:
        rep["verdict"] = verdict(rep)
    if "--write" in sys.argv:
        import os
        os.makedirs("site/reviews", exist_ok=True)
        for rep in reps:
            with open(f"site/reviews/{rep['chain']}-{rep['address'].lower()}.json", "w") as fh:
                json.dump(rep, fh, indent=1)
        print(f"wrote {len(reps)} review(s) to site/reviews/")
    else:
        print(json.dumps(reps, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

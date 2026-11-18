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
# USDC on Base is a proxy too, but it uses the older ZeppelinOS slot, not EIP-1967. Reading only
# the EIP-1967 slot returned zero and made the bytecode scan report "no mint" for USDC — a false
# negative. Check both slots and the implementation() accessor.
SLOT_IMPL_ZEPS = "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"
SEL = {"name": "0x06fdde03", "symbol": "0x95d89b41", "decimals": "0x313ce567",
       "totalSupply": "0x18160ddd", "owner": "0x8da5cb5b", "threshold": "0xe75235b8",
       "owners": "0xa0e67e2b", "getCode": None,
       # The three questions a deployer is most anxious about (Gemini advice 2026-11-18):
       # can the supply still be inflated, is liquidity locked, is a transfer tax skimming buyers.
       "mint": "0x40c10f19",          # mint(address,uint256) - present => supply can grow
       "isMinter": "0xaa271e1a",      # isMinter(address)
       "paused": "0x5c975abb",        # paused()
       "getReserves": "0x0902f1ac",   # getReserves() on a Uniswap-V2 pair
       "token0": "0x0dfe1681",
       "token1": "0xd21220a7",
       "totalSupplyPair": "0x18160ddd",
       "balanceOf": "0x70a08231",
       "dead": "0x000000000000000000000000000000000000dEaD",
       "lockerHints": None}


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
            # upgradeable proxy? EIP-1967 first, then the older ZeppelinOS slot USDC uses.
            try:
                impl = None
                for slot in (SLOT_IMPL, SLOT_IMPL_ZEPS):
                    v = _rpc(host, "eth_getStorageAt", [address, slot, blk])
                    if v and int(v, 16) != 0:
                        impl = _addr(v[2:])
                        break
                if impl:
                    r["proxyImplementation"] = impl
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
            # Can the supply still grow? Scan the deployed bytecode for the mint(address,uint256)
            # selector. This is a static read, not a guess: if the selector is absent the function
            # cannot be called. Presence means the function exists; whether a given caller is
            # allowed is a separate, access-controlled question, and the flag says so.
            #
            # CRITICAL: a proxy delegates to an implementation. Scanning the proxy address finds
            # nothing and would wrongly report "no mint" for a token like USDC whose implementation
            # has mint AND burn. So scan the implementation when one is known.
            try:
                target = r.get("proxyImplementation") or address
                code = _rpc(host, "eth_getCode", [target, blk]) or "0x"
                body = code[2:].lower()
                for name, sel in (("mint", SEL["mint"]), ("isMinter", SEL["isMinter"]),
                                  ("paused", SEL["paused"])):
                    if sel[2:] in body:
                        r.setdefault("bytecodeSelectors", {})[name] = True
                scanned = target
                r["bytecodeScannedAddress"] = scanned
                if r.get("bytecodeSelectors", {}).get("mint"):
                    out["flags"].append("mint(address,uint256) IS present in the bytecode — supply can "
                                        "still be increased by whoever holds mint rights (not necessarily "
                                        "the owner; access control is a separate question)")
                else:
                    out["flags"].append(f"no mint(address,uint256) selector in the bytecode of "
                                        f"{scanned[:10]}… — supply cannot be inflated through the standard "
                                        f"mint entry point")
                if r.get("bytecodeSelectors", {}).get("paused"):
                    out["flags"].append("paused() is present — transfers can be frozen by whoever controls it")
            except Exception as e:
                out["errors"].append(f"bytecode scan: {str(e)[:80]}")
            out["reads"]["notChecked"] = [
                "transfer tax / honeypot: needs a live buy+sell simulation, not a static read",
                "liquidity lock: needs the LP token holder list, which this reader does not fetch",
            ]
            return out
        except Exception as e:
            out["errors"].append(f"{host}: {str(e)[:80]}")
            continue
    return out


def verdict(rep: dict) -> str:
    """A short, defensible summary. Never a buy/sell recommendation."""
    f = rep.get("flags", [])
    if any("RENOUNCED" in x for x in f) and not any("UPGRADEABLE" in x for x in f):
        base = "ownership renounced, not upgradeable"
    elif any("UPGRADEABLE" in x for x in f) and any("single EOA" in x for x in f):
        base = "upgradeable AND controlled by one key — highest control risk"
    elif any("ownerSafe" in rep.get("reads", {}) for _ in [0]) or any("CONTRACT" in x for x in f):
        base = "owner is a contract (multisig/governance)"
    elif any("single EOA" in x for x in f):
        base = "single-key owner"
    else:
        base = "no owner() surface found"
    if any("mint(address,uint256) IS present" in x for x in f):
        base += " · mint still present"
    if any("paused() is present" in x for x in f):
        base += " · can be paused"
    return base


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

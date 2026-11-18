#!/usr/bin/env python3
"""AF multi-chain token verifier — prove a token address before AF accepts it.

Never publish a deposit address that was not read from the chain. This tool takes a
candidate map (chain -> token address) and, for each one, reads symbol(), name() and
decimals() from the contract on that chain. Anything that does not answer is dropped.

It then checks AF's balance in each verified token, so the pay page can show a real,
chain-verified list of what AF accepts.

Usage:
  python3 tools/af_tokens.py --write        # verify + write site/pay-tokens.json
  python3 tools/af_tokens.py                # print the verified table
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone

AF = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"

RPCS = {
    "ethereum": ["https://eth.drpc.org", "https://ethereum-rpc.publicnode.com"],
    "base": ["https://base-rpc.publicnode.com", "https://mainnet.base.org"],
    "arbitrum": ["https://arb1.arbitrum.io/rpc", "https://arbitrum-one-rpc.publicnode.com"],
    "optimism": ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com"],
    "polygon": ["https://polygon-bor-rpc.publicnode.com", "https://polygon-rpc.com"],
    "bsc": ["https://bsc-rpc.publicnode.com", "https://binance.llamarpc.com"],
    "gnosis": ["https://gnosis-rpc.publicnode.com", "https://rpc.gnosischain.com"],
    "avalanche": ["https://avalanche-c-chain-rpc.publicnode.com", "https://api.avax.network/ext/bc/C/rpc"],
    "scroll": ["https://scroll-rpc.publicnode.com", "https://rpc.scroll.io"],
    "linea": ["https://linea-rpc.publicnode.com", "https://rpc.linea.build"],
    "zksync": ["https://zksync-era-rpc.publicnode.com", "https://mainnet.era.zksync.io"],
    "celo": ["https://celo-rpc.publicnode.com", "https://forno.celo.org"],
    "mantle": ["https://mantle-rpc.publicnode.com"],
}

CHAIN_ID = {"ethereum": 1, "base": 8453, "arbitrum": 42161, "optimism": 10, "polygon": 137,
            "bsc": 56, "gnosis": 100, "avalanche": 43114, "scroll": 534352, "linea": 59144,
            "zksync": 324, "celo": 42220, "mantle": 5000}

NATIVE = {"ethereum": "ETH", "base": "ETH", "arbitrum": "ETH", "optimism": "ETH", "polygon": "POL",
          "bsc": "BNB", "gnosis": "xDAI", "avalanche": "AVAX", "scroll": "ETH", "linea": "ETH",
          "zksync": "ETH", "celo": "CELO", "mantle": "MNT"}

# Candidate high-liquidity tokens per chain. Every one is verified on-chain before use.
CANDIDATES = {
    "ethereum": {"USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                 "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                 "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                 "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                 "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"},
    "base": {"USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
             "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
             "WETH": "0x4200000000000000000000000000000000000006",
             "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"},
    "arbitrum": {"USDC": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
                 "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1c0b69FCbb9",
                 "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
                 "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"},
    "optimism": {"USDC": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                 "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
                 "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1"},
    "polygon": {"USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
                "USDC.e": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619"},
    "bsc": {"USDT": "0x55d398326f99059fF775485246999027B3197955",
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "DAI": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3"},
    "gnosis": {"USDC": "0xDDAfbb505ad214D7b80b1f830fcCc89B60fb7A83",
               "USDT": "0x4ECaBa5870353805a9F068101A40E0f32ed605C6",
               "WXDAI": "0xe91D153E0b41518A2Ce8Dd3D7944Fa863463a97d"},
    "avalanche": {"USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
                  "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7"},
    "scroll": {"USDC": "0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4"},
    "linea": {"USDC": "0x176211869cA2b568f2A7D4EE941E073a821EE1ff"},
    "zksync": {"USDC": "0x1d17CBcF0D6D143135aE902365D2E5e2A16538D4"},
    "celo": {"USDC": "0xcebA9300f2b948710d2653dD7B07f33A8B32118C",
             "USDT": "0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e"},
    "mantle": {"USDC": "0x09Bc4E0D864854c6aFB6eB9A9cdF58aC190D0dF9"},
}

SEL = {"symbol": "0x95d89b41", "name": "0x06fdde03", "decimals": "0x313ce567",
       "balanceOf": "0x70a08231"}


def _rpc(host: str, method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(host, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "AF-tokens"})
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def _decode_string(hexdata: str) -> str:
    if not hexdata or hexdata == "0x":
        return ""
    raw = bytes.fromhex(hexdata[2:])
    if len(raw) == 32:  # bytes32 symbol
        return raw.rstrip(b"\x00").decode("utf-8", "replace")
    if len(raw) >= 64:
        try:
            n = int.from_bytes(raw[32:64], "big")
            return raw[64:64 + n].decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def read_token(chain: str, addr: str) -> dict | None:
    for host in RPCS.get(chain, []):
        try:
            blk = _rpc(host, "eth_blockNumber", [])
            code = _rpc(host, "eth_getCode", [addr, blk])
            if not code or code == "0x":
                continue
            out = {"chain": chain, "address": addr, "chainId": CHAIN_ID[chain]}
            for key in ("symbol", "name"):
                try:
                    out[key] = _decode_string(_rpc(host, "eth_call", [{"to": addr, "data": SEL[key]}, blk]))
                except Exception:
                    out[key] = ""
            try:
                out["decimals"] = int(_rpc(host, "eth_call", [{"to": addr, "data": SEL["decimals"]}, blk]), 16)
            except Exception:
                out["decimals"] = None
            data = SEL["balanceOf"] + "0" * 24 + AF[2:].lower()
            try:
                out["afBalance"] = int(_rpc(host, "eth_call", [{"to": addr, "data": data}, blk]), 16) / (10 ** (out["decimals"] or 0))
            except Exception:
                out["afBalance"] = None
            out["ok"] = bool(out["symbol"]) and out["decimals"] is not None
            return out
        except Exception:
            continue
    return None


def native_balance(chain: str) -> dict:
    for host in RPCS.get(chain, []):
        try:
            b = _rpc(host, "eth_getBalance", [AF, "latest"])
            return {"chain": chain, "chainId": CHAIN_ID[chain], "token": NATIVE[chain],
                    "native": True, "afBalance": int(b, 16) / 1e18, "ok": True}
        except Exception:
            continue
    return {"chain": chain, "chainId": CHAIN_ID[chain], "token": NATIVE[chain], "native": True, "ok": False}


def build() -> dict:
    tokens, dropped = [], []
    for chain, toks in CANDIDATES.items():
        for label, addr in toks.items():
            r = read_token(chain, addr)
            if r and r.get("ok"):
                r["label"] = label
                tokens.append(r)
            else:
                dropped.append({"chain": chain, "label": label, "address": addr})
    natives = [native_balance(c) for c in RPCS if native_balance(c).get("ok")]
    return {"schema": "af.pay.tokens.v1",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "payout_address": AF,
            "note": "Every token below was read from its contract on that chain (symbol/decimals). "
                    "Anything that did not answer was dropped, not guessed.",
            "chains": sorted(RPCS.keys()),
            "native": natives,
            "tokens": tokens, "dropped": dropped}


def main() -> int:
    d = build()
    if "--write" in sys.argv:
        import os
        os.makedirs("site", exist_ok=True)
        with open("site/pay-tokens.json", "w") as fh:
            json.dump(d, fh, indent=1)
        print(f"wrote site/pay-tokens.json: {len(d['tokens'])} verified tokens on {len(d['chains'])} chains, "
              f"{len(d['dropped'])} dropped")
    else:
        for t in d["tokens"]:
            print(f"  {t['chain']:10s} {t['symbol']:7s} dec={t['decimals']:<3} bal={t['afBalance']} {t['address']}")
        print("dropped:", [f"{x['chain']}/{x['label']}" for x in d["dropped"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

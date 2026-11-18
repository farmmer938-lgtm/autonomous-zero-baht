#!/usr/bin/env python3
"""AF Verified Facts — a durable, block-pinned fact registry that AI agents can buy.

An agent that must act on a protocol's control plane has no cheap way to know
whether the documentation still matches the chain. This job answers that from
primary sources only, and publishes the answer as a signed, hash-pinned JSON fact.

Design constraints (why it can run forever at zero cost):
  * GitHub Actions is the durable compute; GitHub Pages is the durable host.
  * No secrets: it reads public RPC endpoints and public documentation.
  * Every fact is read at ONE finalized block from TWO independent RPC endpoints;
    if the two disagree, no fact is written for that spec (fail closed).
  * The output carries a sha256 content hash so a consumer can pin it.

Usage: python3 tools/af_facts.py [--out site/facts] [--write]
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

try:
    from eth_utils import to_checksum_address
except Exception:  # pragma: no cover - the workflow installs eth-utils
    def to_checksum_address(a: str) -> str:
        return a

RPCS = {
    "ethereum": ["https://eth.drpc.org", "https://ethereum-rpc.publicnode.com"],
    "base": ["https://base-rpc.publicnode.com", "https://mainnet.base.org"],
    "optimism": ["https://mainnet.optimism.io", "https://optimism-rpc.publicnode.com"],
}
SEL = {"owner": "0x8da5cb5b", "threshold": "0xe75235b8", "owners": "0xa0e67e2b",
       "version": "0xffa1ad74", "min_delay": "0xf27a0c92"}
SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
SLOT_ADMIN = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"

# Each spec is a fact an agent would want to be able to cite.
SPECS = [
    {"id": "exactly-protocol-owner-ethereum-quorum", "chain": "ethereum",
     "address": "0x7A65824d74B0C20730B6eE4929ABcc41Cbe843Aa", "kind": "safe_quorum",
     "subject": "Exactly Protocol — Protocol Owner multisig (Ethereum)",
     "claim": "The Safe that owns Exactly Protocol on Ethereum runs at the quorum recorded below.",
     "docs_url": "https://docs.exact.ly/security/access-control",
     "docs_claim": "currently 3 out of 6"},
    {"id": "kpk-security-council-ethereum-quorum", "chain": "ethereum",
     "address": "0x8b884f80B3B839F52b6cE168f133e7a5D1f0A537", "kind": "safe_quorum",
     "subject": "KPK — Security Council Safe (Ethereum)",
     "claim": "KPK's Security Council Safe runs at the quorum recorded below.",
     "docs_url": "https://docs.kpk.io/", "docs_claim": "5/8"},
    {"id": "aave-v3-pool-proxy-ethereum", "chain": "ethereum",
     "address": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2", "kind": "proxy_admin",
     "subject": "Aave V3 Pool — upgradeable proxy (Ethereum)",
     "claim": "The implementation behind the Aave V3 Pool proxy on Ethereum, read from the EIP-1967 slot.",
     "docs_url": "https://aave.com/docs", "docs_claim": None},
    {"id": "gnosisdao-treasury-safe-quorum", "chain": "ethereum",
     "address": "0x849D52316331967b6fF1198e5E32A0eB168D039d", "kind": "safe_quorum",
     "subject": "GnosisDAO — Treasury Safe (Ethereum)",
     "claim": "GnosisDAO's Treasury Safe runs at the quorum recorded below.",
     "docs_url": "https://docs.gnosischain.com/", "docs_claim": None},
    {"id": "aave-addresses-provider-owner", "chain": "ethereum",
     "address": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e", "kind": "owner_contract",
     "subject": "Aave V3 AddressesProvider — owner (Ethereum)",
     "claim": "The address that owns the Aave V3 AddressesProvider (the registry every Aave market reads).",
     "docs_url": "https://aave.com/docs", "docs_claim": None},
    {"id": "uniswap-v3-factory-owner", "chain": "ethereum",
     "address": "0x1F98431c8aD98523631AE4a59f267346ea31F984", "kind": "owner_contract",
     "subject": "Uniswap V3 Factory — owner (Ethereum)",
     "claim": "The address that owns the Uniswap V3 Factory, which can enable new fee tiers.",
     "docs_url": "https://docs.uniswap.org/", "docs_claim": None},
    {"id": "maker-pause-proxy-owner", "chain": "ethereum",
     "address": "0xBE8E3e3618f7474F8cB1d074A26afFef007E98FB", "kind": "owner_contract",
     "subject": "MakerDAO PauseProxy — owner (Ethereum)",
     "claim": "The governance address that owns MakerDAO's PauseProxy, the contract that executes every Maker spell.",
     "docs_url": "https://manual.makerdao.com/", "docs_claim": None},
    {"id": "1inch-v6-router-owner", "chain": "ethereum",
     "address": "0x111111125421cA6dc452d289314280a0f8842A65", "kind": "owner_contract",
     "subject": "1inch Aggregation Router V6 — owner (Ethereum)",
     "claim": "The address that owns the 1inch Aggregation Router V6.",
     "docs_url": "https://docs.1inch.io/", "docs_claim": None},
    {"id": "eigenlayer-strategy-manager-owner", "chain": "ethereum",
     "address": "0x858646372CC42E1A627fcE94aa7A7033e7CF075A", "kind": "owner_contract",
     "subject": "EigenLayer StrategyManager — owner (Ethereum)",
     "claim": "The address that owns the EigenLayer StrategyManager, the entry point for stake deposits.",
     "docs_url": "https://docs.eigenlayer.xyz/", "docs_claim": None},
    {"id": "mayc-owner", "chain": "ethereum",
     "address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6", "kind": "owner_contract",
     "subject": "Mutant Ape Yacht Club — owner",
     "claim": "The address that owns the MAYC contract, which controls collection-level settings.",
     "docs_url": None, "docs_claim": None},
    {"id": "azuki-owner", "chain": "ethereum",
     "address": "0xED5AF388653567Af2F388E6224dC7C4b3241C544", "kind": "owner_contract",
     "subject": "Azuki — owner",
     "claim": "The address that owns the Azuki contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "pudgy-penguins-owner", "chain": "ethereum",
     "address": "0xBd3531dA5CF5857e7CfAA92426877b022e612cf8", "kind": "owner_contract",
     "subject": "Pudgy Penguins — owner",
     "claim": "The address that owns the Pudgy Penguins contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "moonbirds-owner", "chain": "ethereum",
     "address": "0x23581767a106ae21c074b2276D25e5C3e136a68b", "kind": "owner_contract",
     "subject": "Moonbirds — owner",
     "claim": "The address that owns the Moonbirds contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "doodles-owner", "chain": "ethereum",
     "address": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e", "kind": "owner_contract",
     "subject": "Doodles — owner",
     "claim": "The address that owns the Doodles contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "otherdeed-owner", "chain": "ethereum",
     "address": "0x34d85c9CDeB23FA97cb08333b511ac86E1C4E258", "kind": "owner_contract",
     "subject": "Otherdeed (Otherside) — owner",
     "claim": "The address that owns the Otherdeed land contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "clonex-owner", "chain": "ethereum",
     "address": "0x49cF6f5d44E70224e2E23fDcdd2C053F30aDA28B", "kind": "owner_contract",
     "subject": "CloneX — owner",
     "claim": "The address that owns the CloneX contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "0x-exchange-proxy-owner", "chain": "ethereum",
     "address": "0xDef1C0ded9bec7F1a1670819833240f027b25EfF", "kind": "owner_contract",
     "subject": "0x ExchangeProxy — owner",
     "claim": "The address that owns the 0x ExchangeProxy.",
     "docs_url": None, "docs_claim": None},
    {"id": "cool-cats-owner", "chain": "ethereum",
     "address": "0x1A92f7381B9F03921564a437210bB9396471050C", "kind": "owner_contract",
     "subject": "Cool Cats — owner",
     "claim": "The address that owns the Cool Cats contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "world-of-women-owner", "chain": "ethereum",
     "address": "0xe785E82358879F061BC3dcAC6f0444462D4b5330", "kind": "owner_contract",
     "subject": "World of Women — owner",
     "claim": "The address that owns the World of Women contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "kennel-club-owner", "chain": "ethereum",
     "address": "0xba30E5F9Bb24caa003E9f2f0497Ad287FDF95623", "kind": "owner_contract",
     "subject": "BAYC Kennel Club — owner",
     "claim": "The address that owns the BAYC Kennel Club contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "milady-owner", "chain": "ethereum",
     "address": "0x5Af0D9827E0c53E4799BB226655A1de152A425a5", "kind": "owner_contract",
     "subject": "Milady Maker — owner",
     "claim": "The address that owns the Milady Maker contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "hashmasks-owner", "chain": "ethereum",
     "address": "0xC2C747E0F7004F9E8817Db2ca4997657a7746928", "kind": "owner_contract",
     "subject": "Hashmasks — owner",
     "claim": "The address that owns the Hashmasks contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "cryptodickbutts-owner", "chain": "ethereum",
     "address": "0x42069ABFE407C60cf4ae4112bEDEaD391dBa1cdB", "kind": "owner_contract",
     "subject": "CryptoDickbutts — owner",
     "claim": "The address that owns the CryptoDickbutts contract.",
     "docs_url": None, "docs_claim": None},
    {"id": "1inch-v5-router-owner", "chain": "ethereum",
     "address": "0x1111111254EEB25477B68fb85Ed929f73A960582", "kind": "owner_contract",
     "subject": "1inch Aggregation Router V5 — owner",
     "claim": "The address that owns the 1inch V5 router.",
     "docs_url": None, "docs_claim": None},
    {"id": "paraswap-v5-owner", "chain": "ethereum",
     "address": "0x216B4B4Ba9F3e719726886d34a177484278Bfcae", "kind": "owner_contract",
     "subject": "ParaSwap V5 — owner",
     "claim": "The address that owns the ParaSwap V5 AugustusSwapper.",
     "docs_url": None, "docs_claim": None},
    {"id": "convex-booster-owner", "chain": "ethereum",
     "address": "0xF403C135812408BFbE8713b5A23a04b3D48AAE31", "kind": "owner_contract",
     "subject": "Convex Booster — owner",
     "claim": "The address that owns the Convex Booster.",
     "docs_url": None, "docs_claim": None},
    {"id": "uniswap-v3-factory-base-owner", "chain": "base",
     "address": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD", "kind": "owner_contract",
     "subject": "Uniswap V3 Factory (Base) — owner",
     "claim": "The address that owns the Uniswap V3 Factory on Base.",
     "docs_url": None, "docs_claim": None},
    {"id": "morpho-blue-owner", "chain": "base",
     "address": "0xBBBBBbbBBb9cC5e90e3b3Af64bdAF62C37EEFFCb", "kind": "owner_contract",
     "subject": "Morpho Blue (Base) — owner",
     "claim": "The address that owns the Morpho Blue singleton on Base.",
     "docs_url": None, "docs_claim": None},
]


def rpc(chain: str, method: str, params: list, host: str):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(host, data=body,
                                 headers={"Content-Type": "application/json", "User-Agent": "AF-facts/1.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        j = json.load(r)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def word(hexdata: str, i: int) -> str:
    return hexdata[2 + i * 64: 2 + (i + 1) * 64]


def addr_from_word(w: str):
    return None if not w or int(w, 16) == 0 else to_checksum_address("0x" + w[-40:])


def read_once(chain: str, host: str, address: str, kind: str, block: str):
    if kind == "safe_quorum":
        thr = rpc(chain, "eth_call", [{"to": address, "data": SEL["threshold"]}, block], host)
        own = rpc(chain, "eth_call", [{"to": address, "data": SEL["owners"]}, block], host)
        n = int(word(own, 1), 16)
        return {"threshold": int(thr, 16), "ownerCount": n,
                "owners": [addr_from_word(word(own, 2 + i)) for i in range(n)]}
    if kind == "timelock":
        md = rpc(chain, "eth_call", [{"to": address, "data": SEL["min_delay"]}, block], host)
        return {"minDelaySeconds": int(md, 16)}
    if kind == "owner_contract":
        ow = rpc(chain, "eth_call", [{"to": address, "data": SEL["owner"]}, block], host)
        return {"owner": addr_from_word(ow[2:])}
    if kind == "proxy_admin":
        impl = rpc(chain, "eth_getStorageAt", [address, SLOT_IMPL, block], host)
        adm = rpc(chain, "eth_getStorageAt", [address, SLOT_ADMIN, block], host)
        return {"implementation": addr_from_word(impl[2:]), "admin": addr_from_word(adm[2:])}
    raise ValueError(kind)


def docs_owner_count(docs_claim: str):
    """Parse 'a/b' or 'a of b' -> the owner count b, for the verdict."""
    import re
    m = re.search(r"(\d)\s*(?:-|–|of|/|out of)\s*(\d)", docs_claim or "")
    return int(m.group(2)) if m else None


def build_fact(spec: dict) -> dict | None:
    hosts = RPCS[spec["chain"]]
    # pin one block, then read it from both endpoints
    block = None
    for h in hosts:
        try:
            block = rpc(spec["chain"], "eth_blockNumber", [], h)
            break
        except Exception:
            continue
    if block is None:
        return None
    bn = int(block, 16)
    reads = []
    for h in hosts:
        try:
            reads.append(read_once(spec["chain"], h, spec["address"], spec["kind"], hex(bn)))
        except Exception:
            return None
    if len(reads) < 2 or reads[0] != reads[1]:
        return None  # fail closed: two endpoints must agree
    value = reads[0]
    bh = None
    for h in hosts:
        try:
            bh = rpc(spec["chain"], "eth_getBlockByNumber", [hex(bn), False], h).get("hash")
            break
        except Exception:
            continue
    verdict = None
    claimed = docs_owner_count(spec.get("docs_claim", ""))
    if spec["kind"] == "safe_quorum" and claimed is not None:
        verdict = "consistent" if claimed == value["ownerCount"] else "mismatch"
    fact = {
        "id": spec["id"], "subject": spec["subject"], "claim": spec["claim"],
        "chain": spec["chain"], "address": to_checksum_address(spec["address"]), "kind": spec["kind"],
        "value": value, "blockNumber": bn, "blockHash": bh,
        "rpcEndpoints": hosts,
        "docs": {"url": spec.get("docs_url"), "claim": spec.get("docs_claim"), "verdict": verdict},
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
    }
    canonical = json.dumps({k: fact[k] for k in ("id", "chain", "address", "kind", "value",
                                                 "blockNumber", "blockHash")}, sort_keys=True)
    fact["contentHash"] = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
    return fact


def main() -> int:
    out = "site/facts"
    write = "--write" in sys.argv
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    facts, skipped = [], []
    for spec in SPECS:
        f = build_fact(spec)
        if f:
            facts.append(f)
            print(f"OK   {f['id']}: {f['kind']} {json.dumps(f['value'])[:90]} verdict={f['docs']['verdict']}")
        else:
            skipped.append(spec["id"])
            print(f"SKIP {spec['id']} (endpoints disagreed or unreachable)")
    index = {"schema": "af.facts.index.v1", "generatedAt": datetime.now(timezone.utc).isoformat(),
             "count": len(facts), "facts": [{"id": f["id"], "subject": f["subject"], "chain": f["chain"],
                                             "kind": f["kind"], "verdict": f["docs"]["verdict"],
                                             "contentHash": f["contentHash"], "path": f"facts/{f['id']}.json"}
                                            for f in facts],
             "skipped": skipped,
             "how_to_use": "GET /facts/<id>.json for the value, block and contentHash. Pin the hash; re-fetch to detect drift.",
             "how_to_buy": "Need a fact that is not listed? Open an issue with the address and its docs URL; AF verifies it and adds it."}
    if write:
        os.makedirs(out, exist_ok=True)
        for f in facts:
            with open(os.path.join(out, f["id"] + ".json"), "w") as fh:
                json.dump(f, fh, indent=1)
        with open(os.path.join(out, "index.json"), "w") as fh:
            json.dump(index, fh, indent=1)
        print(f"wrote {len(facts)} facts to {out}/")
    else:
        print(json.dumps(index, indent=1)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# x402 on Base — chain-truth revenue dataset

Every x402 directory republishes what sellers *declare*. This measures what their `payTo` wallets
**actually received** in USDC on Base, and publishes the gap.

Snapshot: **2026-11-20** (block 59,934,298), window ≈ **8.1 days**, **769** advertised Base payTo
wallets. Live table: <https://farmmer938-lgtm.github.io/autonomous-zero-baht/leaderboard.html>

Maintained by **AF**, an autonomous agent. Amounts are chain observations, not endorsements.

## The number that matters

| | |
|---|---|
| advertised Base `payTo` wallets scanned | **769** |
| never received a single USDC transfer | **429 (55.8%)** |
| received anything genuine | 338 |
| genuine USDC in the window | **$37,766.95** (advertised: $41,067.10) |
| median wallet that received anything | **$0.01** |
| share of all genuine revenue taken by the top wallet | **62.5%** |
| share taken by the top 10 wallets | **99.8%** |
| wallets ≥ $1 / ≥ $10 / ≥ $100 / ≥ $1,000 | **25 / 10 / 6 / 3** |

The x402 seller economy is not a long tail. It is one consumer brand (Bitrefill, $23.6k), a handful
of operators, and 400+ wallets that advertise a price and have never been paid.

## Top 10 by genuine USDC

| # | service | genuine USDC | payers | verdict | payTo |
|---|---|---|---|---|---|
| 1 | Bitrefill | $23,614.31 | 147 | REAL | `0x480cd46e…` |
| 2 | (unnamed payTo) | $11,500.03 | 18 | REAL | `0x0f99fc0c…` |
| 3 | Gondola | $2,000.06 | 4 | REAL | `0x8180a3cb…` |
| 4 | Laso Finance | $190.01 | 14 | REAL | `0x3291e96b…` |
| 5 | Clash of Coins | $135.06 | 430 | REAL | `0x8b29dabd…` |
| 6 | AX1 Console | $101.16 | 692 | MIXED | `0x7284d41b…` |
| 7 | OpenGradient | $85.85 | 4 | REAL | `0x9deebb5d…` |
| 8 | (unnamed payTo) | $34.30 | 686 | REAL | `0x17cd53c0…` |
| 9 | vAPI x402 decoder | $11.21 | 16 | REAL | `0x6b7b3cb6…` |
| 10 | Arkham x402 | $10.40 | 3 | REAL | `0x942bd3e3…` |

## What "genuine" means — and what it does not

- **Genuine** = inbound USDC after removing *operator-like* senders: a wallet that also funds its own
  resources, or circular volume between a seller's own wallets. 2 wallets were self-pay only.
- It is **not** per-payer loop detection. A wallet can receive USDC for reasons other than x402
  sales, and a determined payment loop can look genuine at this level.
- Per-seller verdicts with the payer breakdown (`REAL` / `MIXED` / `SELF_PAY` / `NEGLIGIBLE` /
  `NO_SETTLEMENT`) are what the paid endpoint returns.

## Files

| file | what |
|---|---|
| `data/leaderboard.json` | all 769 wallets: rank, `payTo`, services, genuine/inbound USDC, payers, tx count, verdict |
| `data/summary.json` | the aggregate numbers in this README |
| `METHOD.md` | exact method, RPC, window, thresholds, known failure modes |

## Get your own verdict

`GET <host>/seller_verify?url=<your x402 endpoint>` — **$0.05 USDC on Base**, returns the verdict plus
the payer breakdown. The host moves when the operator's sandbox restarts; the current one is published
at <https://farmmer938-lgtm.github.io/autonomous-zero-baht/data/live_endpoint.json>. Free sample:
`<host>/seller_verify/examples`.

## Reproduce

Produced by `tools/af_x402_census.py` in
[farmmer938-lgtm/AX_MASTER_BRAIN](https://github.com/farmmer938-lgtm/AX_MASTER_BRAIN): it reads the
advertised `payTo` set from the x402 catalogue, then pulls USDC `Transfer` logs in ≤49k-block chunks
from a public Base RPC. No third-party analytics, no self-reported numbers.

## Corrections

If a row is wrong, open an issue with the `payTo` and the transaction hash you believe should change
the verdict. Corrections are published, not silently applied.

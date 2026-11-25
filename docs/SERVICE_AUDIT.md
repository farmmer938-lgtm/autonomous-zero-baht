# The service AF actually delivers (checked 2026-11-25)

## One sentence

A Base token's on-chain facts — owner, mint authority, supply, liquidity, concentration —
each with the block it was read at and the command that reproduces it, replied inside the
GitHub issue you opened.

## Why this and not "the audit in the catalogue"

`site/af-catalog.json` lists `POST /audit` at **$49**, served by the x402 cashier. That
cashier has no server in this repository and its host answers **404** (see PR #68). A $49
product behind a dead endpoint is not a product. The same engine that produced the **227
reports in `site/reviews/`** runs without a server, so the offer moved to the one rail that
cannot die: **a GitHub issue in, a report out**.

## What is delivered

| field | source | reproducible by |
|---|---|---|
| chain, address, block | RPC `eth_blockNumber` + `eth_getCode` | quote the block |
| `name`, `symbol`, `decimals`, total supply | ERC-20 calls at that block | same block, same calls |
| owner, and what kind of address it is | `owner()` when it exists; EOA vs contract | `eth_getCode(owner)` |
| mint authority | supply changes / owner privilege read | re-read at the next block |
| liquidity | DEX pool reserves, pool named | pool address in the report |
| holder concentration | free holder data where available | source named |
| what could **not** be read | listed, never guessed | — |

Delivered as: a markdown comment on the order issue, plus the JSON report committed to
`site/reviews/` so the buyer can diff two runs.

## What is not delivered (and is not claimed)

- honeypot / transfer-tax **simulation** (needs a live buy+sell, which needs capital)
- liquidity-lock proof (needs the LP holder list)
- source-code review or a security audit (different discipline)
- price prediction, investment advice
- any promise that a token is safe

The existing report format already states these limits in `reads.notChecked` — that field is
why this offer is honest, and it stays.

## Price

| tier | price | rationale |
|---|---|---|
| micro | **0.50 USDC** | impulse price for a creator who is about to launch; already the `MICRO_TIER` in `tools/af_selfserve.py` |
| standard | 15 USDC | full token review `TIERS["base"]`, needs a buyer who asks for depth |
| x402 | parked | no server; see PR #68 |

`tests/test_audit_offer.py` fails the build if the sales page quotes a price the cashier does
not charge, or a pay-to address the verifier does not watch.

## Cost and margin

| line | cost |
|---|---|
| hosting, CI, RPC | 0 (GitHub free tier + public RPC) |
| inference | 0 to AF's wallet (runs inside the agent session) |
| **gross margin per 0.50 USDC sale** | **0.50 USDC** |

The only real cost is the agent's time, which is why the price can be 0.50 instead of 49.

## Where a buyer comes from (verified channels only)

`data/acquisition_channels.json` records what AF can publish on without a new account:
GitHub Pages (own site), GitHub issues (the order rail), GitHub repository itself. Farcaster
is **read-only** — posting needs an FID and a signer key AF does not have, and registering
one costs money. No X, Reddit, Discord, or directory account exists, and creating one is
forbidden by the operating rules.

That is the honest bottleneck: AF can build the shop, but has no street.

# Method

## 1. Advertised set
The `payTo` set comes from the public x402 catalogue: every resource declaring `network =
eip155:8453` (Base) contributes its `payTo` address. 769 distinct wallets advertised at least one
Base resource at snapshot time.

## 2. Chain truth
For each wallet, pull USDC `Transfer` logs on Base
(`0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`, topic
`0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef`) where the wallet is the
`to` topic.

- RPC: public Base endpoint; `eth_getLogs` is capped at 50k blocks, so the window is walked in
  49k-block chunks.
- Window: 350,000 blocks (~8.1 days at 2s blocks), ending at the snapshot head block.
- Batching: up to 50 wallets per call via an OR list on `topics[2]`.

Measured RPC traps: `base.blockscout.com` returns Cloudflare 403; drpc caps `getLogs` at 100 blocks;
blockpi returns 503; tenderly/blastapi reject wide spans.

## 3. Operator removal
A sender is treated as *operator-like* when it is the seller's own funding path or part of circular
volume between wallets controlled by the same seller. That USDC is subtracted before ranking.
Wallets with operator volume but no remaining inbound are labelled `SELF_PAY`.

## 4. Verdicts

| verdict | rule |
|---|---|
| `NO_SETTLEMENT` | no inbound transfer at all |
| `SELF_PAY` | inbound exists, all of it operator-like |
| `NEGLIGIBLE` | genuine < $1.00 |
| `REAL` | genuine share ≥ 0.50, ≥ 3 independent payers, genuine ≥ $5.00 |
| `MIXED` | everything else with genuine ≥ $1.00 |

The paid `seller_verify` endpoint uses the same thresholds, so the free table and the paid answer
cannot disagree about what "real" means. The paid call adds per-payer analysis (a wallet paying one
seller ≥ 20 times in 7 days is a loop) and the payer list.

## 5. Failure modes this method does not remove
- A seller can receive USDC for reasons unrelated to x402 (treasury transfers, refunds, other
  products on the same wallet).
- A patient payment loop with fresh wallets per payment looks genuine here.
- Service-name attribution relies on the catalogue's `payTo` mapping; unnamed wallets stay unnamed
  rather than being guessed.
- The window is short by design: it answers "is this wallet being paid *now*", not lifetime revenue.

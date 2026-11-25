# H2 — the Frantic "$10 funded" bounty: what it really is

Checked 2026-11-25 against `https://gofrantic.com/v1/board` and
`https://gofrantic.com/v1/bounties/p-ce0199eecf` (read-only, no claim, no payment).

## The board says

```
#97  price $10  funded=true  work_status=open  claim_slots={capacity:5, occupied:3, available:2}
"Your first bounty is on the house ($10 back when it clears, first five)"
actions.claim = {available: true, state: "requires_identity"}
```

## The detail says something different

The $10 is **not paid to whoever does the work**. It is a rebate for the person who
*funds* a bounty:

> Bring real work through the door, fund it ($10 or more), and let the town complete it: a
> different worker claims your bounty, delivers, is judged, and gets PAID from your funds.
> Once your bounty has cleared to a real worker, claim your $10 back.

Acceptance requires all of:

1. the posting went through `https://gofrantic.com/post` and **passed screening**,
2. the posting price is **$10 or more**, funded by you (`payer_ref=operator:<you>`),
3. the posting **cleared**: a payout receipt exists, paid to a worker **who is not you**
   (different operator, agent and payout wallet),
4. two receipt refs are submitted: your funding receipt (`hfr_…`) and the worker's payout
   receipt, both resolving on the ledger,
5. `evidence_json` includes `claim_type=cleared_posting`, the posting number, `price_cents`,
   both receipt refs, and how the worker is independent of you.

Rejection rules include self-dealing: funding a bounty and steering it to a second identity
you control forfeits the rebate.

## The history on that posting

```
claim_progress: {paid: 1, accepted: 0, delivered: 2, rejected: 9, expired: 96, revising: 0}
```

**1 paid out of 108 attempts** (`success_rate = 0.009`). 96 claims expired, 9 were rejected.

## What it costs AF

| line | amount |
|---|---|
| fund a ≥$10 bounty | **−$10.00** |
| platform fee (`fee_usd`) | −$0.50 |
| rebate if it clears | +$10.00 |
| **net** | **−$0.50, and the $10 leaves first** |

`tools/af_opportunity_rank.py` therefore scores it **`loss`**, not a lead:

```
loss  frantic  net=0.0  rate=0.009  Your first bounty is on the house …
      :: gross 10.0 minus cost 10.0 leaves 0.0
```

## Decision

**Do not claim it.** It violates two operating rules at once: it needs capital AF does not
have (the wallet holds 0.010038 USDC) and it needs a financial transaction nobody authorised.
The `requires_identity` gate is real but secondary — even with an identity the arithmetic does
not work.

## What would make it worth revisiting

- a bounty that pays **for work**, not for funding work (`price_usd` paid to the worker),
- `claim_progress.paid > 0` with a low `expired` count,
- no identity gate, or an identity K already has.

## What K would have to do, if a real Frantic bounty ever appears

1. **Identity** — the claim action is `requires_identity`; only K can complete it. AF cannot
   and must not.
2. **Payout wallet** — Frantic pays to a wallet bound to the operator. It must not be AF's
   trading wallet (`0xf3C9…7702`) if the funds are meant to stay separate.
3. **Nothing else** — claiming, delivering and evidence submission are all API calls AF can
   make once the identity exists.

## Related finding

The radar (`engine/public_watch.py`) shows this posting as the only `funded` row out of 140.
"Funded" is true and still misleading: the money is real, but it is a rebate, not a wage.
`af_opportunity_rank.py` is the tool that separates those two readings.

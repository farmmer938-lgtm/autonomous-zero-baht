# Phase N — First Customer Acquisition

## 0. The advisory council does not exist in this repository

K's instruction: *"ห้ามอ้างว่าปรึกษาทีมแล้ว หากไม่ได้เรียกใช้งานจริง"* and *"ห้ามสร้างสมาชิกปลอม"*.

What I searched, and what I found:

```
ls tools/ | grep -iE "advis|council|board|panel|quorum"     → no match
grep -rln "advisory|advisor|council|quorum" --include=*.py   → tools/af_facts.py (a token-facts
                                                               tool, unrelated)
find / -maxdepth 4 -iname "*council*" | -iname "af_advisor*"  → nothing
ls /workspace                                                 → project, only
```

The `MEMORY.md` line about an "advisor quorum" belongs to a different project in a previous
sandbox; there is no six-role advisory team here, no definitions, no credentials for one.

**So this document is not a council.** It is one agent writing under six headings, and every
line below is labelled with the evidence it stands on. Creating a real council needs a decision
K has not made (an LLM budget for six conversations per phase, or files that call a local model).
Until then, claiming "the council reviewed this" would be the exact fabrication K forbade.

---

## N1 — status, from GitHub itself

```
gh pr view 83 --json mergeCommit → 2c5cbb407eb4508a3bc0b31231c550aacd540280
                                  mergedAt 2026-11-25T15:40:48Z
git log -1                       → 2c5cbb4 M1-M6: a link preview is not a visitor (#83)
```

## N2 — Strategy (one analyst, evidence attached)

**Continue, but stop building.** Evidence: 322 tests, 9 pages served, 3 case studies, 3 guides —
none of which has produced a visit, an enquiry or a payment. Every remaining blocker measured in
Phases J–M was *permission or audience*, never capability. A seventh feature has the same expected
revenue as the sixth: zero.

Stop rule I propose and will follow: **no new feature until a stage above `published` moves.**

## N3 — Market Research

Carried from `data/market_probe.json` (measured 2026-11-25, read-only):

| market | demand evidence found | verdict |
|---|---|---|
| GitHub issues ("mint authority", "renounce ownership", "token audit") | 44 keyword hits, **0** real requests, 1 was our own issue | no buyers visible |
| Farcaster search | bot "Knowledge Drop" series; 4 genuine pain signals, all about **honeypots** | pain exists, wrong product |
| Nostr (earlier) | 790 events/48h, 0 paid requests | no buyers |

**The mismatch, stated plainly:** the market asks *"can I sell this token?"*; AF answers *"who can
change it, at block N"*. AF has no capital to swap and must not guess.

## N4 — Technical (does AF answer the target group?)

| group | answers their question today? |
|---|---|
| developer reviewing a contract | **yes** — owner, owner type, supply, upgradeability, at a block, with a sha256 |
| community moderator | **yes** — the hashed report is the citable artefact a badge cannot be |
| buyer checking a token | **partly** — ownership yes, honeypot no, and the report says so |
| token creator wanting to look clean | **no** — they want an assurance; AF refuses to certify |

Technical honesty gap that matters for sales: **AF cannot answer the most-asked question
(honeypot).** Any pitch that implies otherwise is a refund waiting to happen.

## N5 — Sales & Growth

| route | executable by AF alone | why not / why |
|---|---|---|
| own Pages + sitemap | yes, already done | no distribution |
| GitHub topics/homepage | **no** — 403 | owner-only |
| Search Console | **no** — account | owner-only |
| Farcaster / Nostr / X / Reddit / Discord | **no** | accounts or paid IDs |
| other repos' threads | **no** — `push: false` | permission wall |
| cold email / DM | **refused** | unsolicited contact, and forbidden by K |

Conclusion: AF has no sales channel it may operate. That is the whole of N5.

## N6 — Finance: the price, and the 750 baht question

What exists in code today:

```
tools/af_selfserve.py:  MICRO_TIER = {"id": "micro_fix", "usdc": 0.5}
site/audit/index.html:  "$0.50 USDC per token", Offer price "0.50" USD
pay-to wallet (page, issue template, order tool):  0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702
site/paid/index.json:   payments: 0, cash_received_usdc: 0
```

There is **no 750 baht price anywhere in the repository** — no page, no template, no tool. It came
from an earlier conversation, not from the product. Two prices in the wild means one of them is a
promise the checkout cannot keep, so:

**One price: 0.50 USDC on Base.** Reasons, in order of weight:
1. it is what the code, the tests, the page, the issue template and the payment watcher already agree on;
2. the wallet is on Base and USDC arrives with no fee and no KYC to receive;
3. 750 THB (≈ $21) is 42× higher, and there is zero willingness-to-pay evidence to justify it;
4. a proof-of-revenue goal is served by any amount; the first payment's size is irrelevant, its existence is not.

A test now fails the build if any page advertises 750 THB or a second price.

Payment rails — what is real, with limitations:

| rail | upfront cost | KYC | fee | note |
|---|---|---|---|---|
| USDC on Base to the existing wallet | 0 | none to receive | 0 to receive, buyer pays gas | currently the only rail wired into the ledger |
| CoW swap (gasless) | 0 | none | solver fee on the swap | exists in `tools/af_cow_swap.py`, not needed for receiving |
| Stripe / PayPal / card | 0 upfront | **yes, owner's KYC** | ~2.9% + fixed | **not approved**, and requires the owner's identity |
| x402 paywall endpoint | 0 | none | 0 | needs a host that outlives the sandbox; not available |

## N7 — the experiment (no capital, no spam, no overclaiming)

Three experiments, each with a pass/fail and a stop rule. All depend on a channel K must open —
that dependency is the finding, not a loophole.

| # | experiment | pass | fail → action |
|---|---|---|---|
| E1 | owner opens Search Console + shares the audit link once | ≥1 impression and ≥1 click in 14 days | stop content work; the bottleneck is not the artefact |
| E2 | 10 free audits of *publicly discussed* tokens, published as pages, no outreach | ≥1 human enquiry within 30 days | stop; product/market fit is not there at 0.50 |
| E3 | price test: 0.50 vs 5 USDC on the same page copy, 30 days each | ≥1 payment at either price | stop; keep the artefact free and stop selling |

E2 is the only one AF can start alone, and it costs nothing but time: pick tokens people are
already arguing about, publish the audit free, with the honest disclaimer. It creates indexable
pages about tokens humans search for — the one distribution mechanism that does not need an
account. It also cannot be called spam, because nothing is sent to anyone.

## N8 — Red Team: where this document is wrong

Written by the same analyst, deliberately against the conclusions above.

1. **"No new feature" is convenient.** It protects me from failing at the hard thing (sales) by
   declaring it blocked. Counter: the block is measurable (`push: false`, 403, no account), not a
   preference.
2. **E2 can degrade into content farming.** 10 pages nobody reads is the same zero as 0 pages.
   Guard: E2 is capped at 10, has a 30-day clock, and must be stopped if `discovered` stays null.
3. **0.50 USDC may be the reason nobody buys.** A price that low reads as "toy" to a moderator
   deciding whether to cite it. We have no data either way — which is why E3 exists and why
   claiming the low price is "correct" would be unjustified.
4. **The mismatch may be fatal, not fixable.** If the market only wants honeypot answers and AF
   cannot do honeypots, the honest conclusion is that this product has no market, not that it
   needs more distribution. I cannot test this without a channel; do not let a later report claim
   the mismatch was "solved" by a share.
5. **`reach: null` will tempt every future session to fill it in.** The test added in Phase M is
   the only thing standing between this project and a flattering fake number.

---

## KPI, today (no evidence → `null`, never a substitute number)

| # | KPI | value | evidence |
|---|---|---|---|
| 1 | humans reached the site | **null** | no analytics (M5) |
| 2 | real enquiries | **0** | 0 human `audit-request` issues |
| 3 | real orders | **0** | 0 non-self-test order records |
| 4 | cash received | **0.00 USDC** | `site/paid/index.json` |
| 5 | cost | **0.00** | free tiers only |
| 6 | net profit | **0.00 USDC** | 4 − 5 |

## What I need from K — and nothing else

| decision | why it is K's | time |
|---|---|---|
| Search Console property for the Pages URL | account | ~3 min |
| Settings → About: homepage + topics | admin permission | ~1 min |
| one share of the audit link | owner's audience | ~1 min |
| approve or refuse a real advisory council (LLM budget) | money | decision only |

Everything else in Phase N is done or measured. After those clicks, E1/E3 become measurable and
this project finally has a number that is not null — one way or the other.

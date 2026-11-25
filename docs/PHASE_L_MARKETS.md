# Phase L — market evidence, measured 2026-11-25

Read-only research. No account, no payment, no message sent. Machine copy: `data/market_probe.json`.

## L1 — GitHub homepage / topics: BLOCKED (approved, but not permitted)

The owner approved adding them. The Actions token still cannot:

```
gh repo edit farmmer938-lgtm/autonomous-zero-baht --add-topic base \
  --homepage https://farmmer938-lgtm.github.io/autonomous-zero-baht/audit/
→ HTTP 403: Resource not accessible by integration
→ topics: []   homepage: null
```

Two ways to finish it, both requiring an approval AF does not have:
- the owner pastes Settings → About (homepage + topics), or
- a PAT with `administration` — **explicitly not approved**, so AF stops here.

## L2/L3 — markets searched by problem, not by product name

Method: GitHub search (`user.type` gives bot truth) + Farcaster public search. Each result was
classified `bot` / `question_with_context` / `unclear`, then the samples were read by hand.

| query | indexed | sampled | "questions" | bots | after reading |
|---|---|---|---|---|---|
| `"mint authority" is:issue` | 9 223 | 30 | 3 | 0 | spec/design docs |
| `"renounce ownership" is:issue` | 648 | 30 | 17 | 1 | dev docs, not buyers |
| `"is this token safe" is:issue` | 1 320 | 30 | 1 | 3 | — |
| `"honeypot" is:issue base` | 5 267 | 30 | 2 | 1 | tool repos |
| `"token audit" is:issue base` | 30 463 | 30 | 1 | 1 | **my own issue #75** |

**Verified demand events ready to pay: 0.** The keyword counts are noise, and one of them is
AF's own self-test — exactly the contamination the funnel excludes.

### The one real finding

Farcaster has genuine pain, and it is not about ownership:

> "farcade token looks like a honeypot. stay safe."
> "I can't possibly be the only one on FC getting honeypot tokens. Is there…"
> "honeypot tracker on base that not only checks apparent honeypots but…"
> "Wen ownership renounced??"

**The market asks "can I sell this token?" (a live buy+sell test). AF answers "who can change
this token, at block N" (a static read).** Those are different products. AF must not claim the
first — it has no capital to swap and would be lying if it guessed.

## L4 — competitors, and where AF is actually different

| tool | what it gives | cost | what it cannot give |
|---|---|---|---|
| GoPlus | honeypot, taxes, holders, owner flags | free API | a block-stamped, hashed report you can cite later |
| Basescan / RPC | raw reads, anyone can repeat | free | an interpretation, or a document |
| DexScreener | price, liquidity, volume | free | anything about control |
| CertiK-style audit | a brand and a PDF | thousands | affordability, speed, or honesty about what was not read |

AF's only defensible difference: **a citable artefact** — the block, the exact calls, a sha256,
and a named list of what was *not* established. Not better detection; better provenance.

## L5 — does today's service fit each segment?

| segment | fits | why |
|---|---|---|
| Web3 developer reviewing a contract | **yes** | exactly what the engine reads; the hash makes it diffable |
| community moderator vetting a token | **yes** | a hashed report is pasteable; a green badge is not |
| buyer deciding whether to buy | **partial** | answers owner/mint/upgrade; honeypot stays unread and is labelled so |
| token creator wanting to look clean | **no** | they are buying an assurance; AF refuses to certify |

## L7/L8 — channels and measurement

| channel | write | note |
|---|---|---|
| own Pages, repo, issues | yes | only surfaces AF can act on |
| Farcaster | no (needs a paid FID) | read-only search works with no account |
| Nostr | no identity | key wiped on rebuild |
| X / Reddit / Discord / Telegram | absent | creating an account is forbidden |

Funnel now separates `reach` (null), `traffic` (null), `bots_filtered`, `enquiries`,
`qualified_interest`, `orders`, `delivered`, `paid`, `net_revenue`, and `referrals` (from an
order record, empty until a real order sets it).

## L10 — where the money most likely is, given zero budget

1. **Community moderators on Base**, because the artefact is the product and they need citable
   proof — but AF cannot reach them without a channel it may write to. Blocked, not unattractive.
2. **Developers reviewing a contract before integrating**, same reason, same block.
3. **Token creators** — the segment with money to spend, and the segment AF's honesty fits worst.

**Recommendation (evidence-based): keep the product where it is.** The bottleneck is not the
product, it is one human-visible link, and the market research did not change that. Adding
features, more pages or more articles would produce commits, not customers. The next honest step
is the owner's two minutes in Settings → About, and one link from wherever the owner already has
an audience. Everything after that is measurable.

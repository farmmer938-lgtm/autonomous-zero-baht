# Phase M — First Human Visibility

Checked 2026-11-25. No account created, no message sent, no PAT requested.

## M1 — the merge and the SHA

```
git log -1 --oneline            → 9630c3c L1-L10: search four markets by their complaint (#82)
gh pr view 82 --json mergeCommit → 9630c3c2ec277336bdc4102a4ceda528f4bbb017  merged 15:21:47Z
```

## M2 — homepage and topics: still not set

```
gh api repos/farmmer938-lgtm/autonomous-zero-baht --jq '{topics,homepage}'
{"homepage": null, "topics": []}
```

Approval does not equal permission: `gh repo edit` answers
`403 Resource not accessible by integration`. The token is scoped to contents/issues, not
administration. AF stops there; asking for a PAT is explicitly out of bounds.

## M3 — the shareable link, and what it does **not** claim

Canonical: `https://farmmer938-lgtm.github.io/autonomous-zero-baht/audit/`

The page now carries Open Graph and Twitter card tags, so a pasted link renders a title,
a one-line description and the canonical URL instead of a bare address. That is all a link
preview does. **A share is not a visit, and a visit is not interest.**

Copy, short:
> Base token audit, 0.50 USDC: who can mint, change or upgrade a token — read at a named block,
> with a hash you can re-check. Not a safety certification.

Copy, for a moderator or developer:
> If you need to know who controls a Base token, this reads `owner()`, whether the owner is a
> contract, the supply and whether it is upgradeable, at a block number it prints. You get the
> raw JSON and a sha256. It says which checks it did not perform. 0.50 USDC, delivered in the
> issue. Free guides here: …/audit/guides/check-a-base-token.html

Both deliberately omit "safe", "audited by", "verified", "honeypot-tested" and any comparison
to CertiK. A share that overstates the product would buy one click and one refund request.

## M4 — public channels AF may already use

| channel | can AF publish | evidence |
|---|---|---|
| its own Pages site | yes | `data/published.json`: 9 pages, 200 |
| its own repo (README, releases, issues) | yes | pushes work, CI green |
| GitHub topics / homepage | **no** | 403 (M2) |
| Farcaster | no | write needs a paid FID |
| Nostr | no | no identity since the rebuild |
| X / Reddit / Discord / Telegram | no | no account, and creating one is forbidden |
| other repos' threads | no | `push: false` on foreign repos |

## M5 — can we measure a real visitor without paying? No.

| option | verdict | why |
|---|---|---|
| Search Console | blocked | needs an account |
| GitHub repo traffic API | **403** `Resource not accessible by integration` | needs admin; also counts repo pages, not the site |
| Cloudflare / GoatCounter / Plausible / Umami | blocked | every one needs a signup, and a signup is an account |
| self-hosted counter | blocked | the sandbox host is ephemeral and dies with the session |
| adding a third-party script that phones home | **refused** | it would track visitors without their consent |

So `discovered`, `reach` and `traffic` stay **null**. They are not zeros and they must not be
greeted into existence by a share.

## M6 — the six stages and the evidence each will accept

| stage | accepted evidence | today |
|---|---|---|
| published | the URL answers | **9** |
| discovered | a search engine says so | `null` (no console, queries blocked) |
| visited | an analytics system that actually counts | `null` (no analytics — M5) |
| interested | a question from a human, not a bot | **0** |
| ordered | an order record that is not a self-test | **0** |
| paid | a confirmed on-chain payment | **0**, net **0.0 USDC** |

Pass criterion for Phase M ("proof a person outside reached the page, separable from bots and
from AF's own checks") **is not met, and cannot be met** until one of these exists: an analytics
account, Search Console, or repo admin access for the traffic API. All three need the owner.

## What would unblock each stage — one row, one decision

| to unblock | the smallest human action | time |
|---|---|---|
| discovered | open Search Console, add the Pages URL as a property | ~3 min, free |
| visited | same property shows impressions and clicks — no extra work | 0 |
| homepage/topics | Settings → About: paste the audit URL + 4 topics | ~1 min |
| reached at all | paste the audit link once where the owner already has an audience | ~1 min |

Each is a click in a browser AF cannot open. None of them is a task AF is refusing; all four are
behind an authentication wall that the rules correctly keep shut.

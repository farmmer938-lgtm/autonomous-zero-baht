# Phase K — status, measured 2026-11-25

Rules in force: no new accounts, no paid services, no personal accounts, PRs only, PR #69 untouched.

| | task | result | evidence |
|---|---|---|---|
| K1 | SEO / discoverability | **8 pages pass a structural audit**; adding meta + canonical + JSON-LD to `index.html`, `store.html`, `reviews.html` cleared the last 8 problems | `data/discoverability.json` → `problems: []` |
| K1 | is the site indexed? | **unknown (`null`)** | no Search Console property; search engines reject automated queries |
| K2 | GitHub discovery fields | **BLOCKED** — `gh repo edit` → `403 Resource not accessible by integration` | topics `[]`, homepage `null` still |
| K3 | community demand | searched GitHub + Farcaster read-only: **no buyer requests found** | `data/demand_probe.json` |
| K4 | free channels | Pages + repo writable; Farcaster/Nostr read-only; X/Reddit/Discord absent | same file |
| K5 | funnel | 8 stages, `reach` null, self-tests excluded, fixtures separate | `data/funnel.json`, tests |
| K6 | first customer | **not reachable from inside the sandbox** — see below | — |
| K7 | 6-hourly report | `revenue_pipeline.yml` runs and commits | Actions |

## K1 — what is provable, and what is not

Proved (`tools/af_discoverability.py`): sitemap parses with 13 URLs, every URL resolves to a
real file, `robots.txt` allows crawlers and mentions the sitemap, every entry page has a unique
title, a description, a canonical URL inside the site, exactly one `h1`, and JSON-LD.

Not proved: indexing. There is no Search Console account and Google/Bing refuse automated
queries from here. The report says `null` with a reason. **Unknown is not "not indexed"**, and
it must not be reported as a traffic number.

## K2 — two fields the owner can fill in ten seconds (or a PAT that can)

```
gh api repos/farmmer938-lgtm/autonomous-zero-baht --jq '{topics, homepage}'
{"topics": [], "homepage": null}
gh repo edit ... --add-topic base  →  HTTP 403 Resource not accessible by integration
```

GitHub topics and the repository homepage are real discovery surfaces: topics are what
GitHub's own search and topic pages index. The Actions token cannot set them. Needs either:

- the owner clicks **Settings → About** and pastes
  `https://farmmer938-lgtm.github.io/autonomous-zero-baht/audit/` plus topics
  `base, token-audit, smart-contract-audit, crypto-security`; or
- a PAT with `administration` scope is added as a secret.

## K3 — the demand search, again

| channel | what was searched | finding |
|---|---|---|
| GitHub | `"audit" "base" in:title`, 109 hits | code/CI audits, not token audits |
| Farcaster | `token audit`, `check token contract`, `is this token safe` via public API | bot "Knowledge Drop" series, hack post-mortems, launches — **0 buyer requests** in hand-read samples |
| Nostr | measured earlier (790 events/48h) | 0 genuine paid requests |

Three social channels, three times the same shape: **agent-to-agent chatter, no buyers.** That
is the most important fact Phase J and K have produced, and it is why more content is not the
answer.

## K6 — why "first customer" cannot be produced from here

Every action that could put this in front of a buyer is either a write outside this repository
(permission: false), a new account (forbidden), or a paid promotion (forbidden). What remains is
the owner's existing reach, which the rules correctly exclude.

So the honest deliverable of Phase K is: the shop is findable-shaped and correct, and the one
missing input is a human-visible link.

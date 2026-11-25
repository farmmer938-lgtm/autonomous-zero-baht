# AUTONOMOUS ZERO-BAHT BUSINESS OS

A zero-budget agent workspace. Two things live here:

1. **A research engine** (`engine/`) — reads public RSS feeds, normalizes and dedupes topics,
   scores intent with transparent rules, ranks opportunities, drafts content in template mode,
   validates drafts, and records decisions. It publishes a static site to GitHub Pages.
2. **Revenue surfaces** (`tools/`) — keyless, account-free ways to be paid in USDC on Base:
   a free machine-readable API, paid deep checks, and fact requests ordered through GitHub
   issues. `docs/` explains the model; `artifacts/` is local scratch and is not committed.

It does **not** promise revenue and does **not** auto-publish to third-party platforms.

## Principles
- No paid APIs, ads, VPS, or new subscriptions. Budget stays THB 0 (`config/system.json`).
- Rule-based/template fallback; no AI API required.
- Research sources are public RSS feeds. Respect source terms and rate limits.
- No fake reviews, invented personal experiences, fake engagement, or mass spam.
- Every money claim must come from the chain or a provider API, never from an assumption.
- All runs write logs and structured JSON.

## Run locally (Python 3.11+ recommended)
```bash
python -m unittest discover -s tests -v
python -m engine.run
```
Outputs are written under `data/`. The workflow uses only the Python standard library; the
`tools/` readers additionally need `eth-utils` when they decode contract reads.
The test suite is side-effect free: it writes only to temporary directories, never to
tracked files under `data/` or `site/`.

## Main workflow
`RESEARCH -> NORMALIZE -> DEDUPE -> SCORE -> RANK -> CREATE DRAFTS -> VALIDATE -> DECIDE -> LOG`

Research scoring is deterministic and auditable:
`opportunity_score = keyword_score + intent_score`.

## Configure
Edit `config/system.json`:
- `rss_feeds`: public RSS/Atom feeds to check
- `keywords`: initial niche/intent terms
- `max_items_per_feed`: limit per run
- `max_drafts_per_run`: cap content generation

No credentials are required for the research engine. Network access is only used to fetch
public RSS feeds. If feeds are unavailable, the workflow logs the failure and continues using
local seed data marked as unverified, which the validator then refuses to publish.

## GitHub Actions — what actually runs
| Workflow | Schedule | State |
|---|---|---|
| `qa.yml` | every push / PR | runs the unit tests |
| `public_watch.yml` | cron `*/10` | GitHub decides the real frequency; recent runs land a few times per day, not every 10 minutes |
| `facts.yml` | cron `*/6h` | refreshes the public artifacts and reports failed steps in the `af-alert` issue |
| `revenue_verify.yml` | cron `*/6h` | reads the wallet's inbound USDC from chain logs |
| `pages.yml` | push to `main`, after each data workflow, every 6h | deploys `site/` to GitHub Pages; a `GITHUB_TOKEN` push does not start another workflow, so the data jobs trigger it explicitly |
| `daily.yml` | cron daily 02:47 UTC | runs the research engine, then commits `data/` and the rebuilt site to `main` |

The scheduled jobs never fail on purpose, so GitHub does not email the owner. Problems are
reported through the `af-alert` issue instead. Failures inside `facts.yml` and
`revenue_verify.yml` are recorded in `data/workflow_health.json` and surfaced in that issue —
a green run is not proof that every step published something.

`tests/test_workflow_safety.py` enforces the rules that a stale branch once broke: no workflow
may print `secrets`/`vars`, use `pull_request_target`, pin an action to a mutable tag, or hide
a failure behind `|| true`.

## What is live, and what is not
- **Live:** the GitHub Pages site, the free `site/api/quick-check.json` feed, the status page.
- **Not live / no revenue:** the x402 cashier runs inside an ephemeral sandbox, so its public
  host changes on every restart; `data/live_endpoint.json` is the pointer to check. Paid
  orders and fact requests have taken **zero** payments. Nothing here should be read as
  income until `data/revenue_verify.json` shows it, and the amount matters as much as the
  verdict label.

## Before publishing
Review each draft for accuracy, source attribution, platform rules, affiliate program terms,
and disclosure requirements. Add only real affiliate links you are authorized to use. Never
claim first-hand experience unless it actually occurred.

## Repository layout
- `engine/`: workflow runner, RSS research, ranking, content templates, validation, logging
- `tools/`: Base chain readers, public API builder, invoice/payment reconciliation
- `config/`: zero-payment guard and settings
- `data/`: generated research, drafts, decisions, logs, ledgers
- `site/`: the static site published by GitHub Pages
- `tests/`: standard-library unit tests (engine and the payment rails)
- `.github/workflows/`: scheduled automation

## License
MIT — see `LICENSE`. Copyright (c) 2026 farmmer938-lgtm.

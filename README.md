# AUTONOMOUS ZERO-BAHT BUSINESS OS

A zero-cost-first starter foundation. It researches public RSS feeds, scores topics with transparent rules, drafts content in template mode, validates drafts, and records decisions. It does **not** promise revenue and does not auto-publish to third-party platforms.

## Principles
- No paid APIs, ads, VPS, or new subscriptions.
- Rule-based/template fallback; no AI API required.
- Research sources are public RSS feeds. Respect source terms and rate limits.
- No fake reviews, invented personal experiences, fake engagement, or mass spam.
- Publishing is a separate, manual approval stage until official platform access and rules are verified.
- All runs write logs and structured JSON.

## Run locally (Python 3.11+ recommended)
```bash
python -m engine.run
```
Outputs are written under `data/`. The workflow uses only the Python standard library.

## Main workflow
`RESEARCH -> SCORE -> CREATE DRAFTS -> VALIDATE -> LOG DECISIONS`

## Configure
Edit `config/system.json`:
- `rss_feeds`: public RSS/Atom feeds to check
- `keywords`: initial niche/intent terms
- `max_items_per_feed`: limit per run
- `max_drafts_per_run`: cap content generation

No credentials are required. Network access is only used to fetch public RSS feeds. If feeds are unavailable, the workflow logs the failure and continues using any available data.

## GitHub Actions
The included workflow runs daily and can be started manually. For automated commits, ensure Actions permissions allow the workflow to write to the repository. GitHub Actions free usage/limits may change; the workflow is designed to skip gracefully rather than use paid services.

## Before publishing
Review each draft for accuracy, source attribution, platform rules, affiliate program terms, and disclosure requirements. Add only real affiliate links you are authorized to use. Never claim first-hand experience unless it actually occurred.

## Repository layout
- `engine/`: workflow runner, RSS research, content templates, validation, logging
- `config/`: zero-payment guard and settings
- `data/`: generated research, drafts, decisions, logs
- `tests/`: standard-library unit tests
- `.github/workflows/`: scheduled automation
# Architecture

RESEARCH -> NORMALIZE -> DEDUPE -> SCORE -> RANK -> CREATE -> VALIDATE -> DECIDE -> LOG

## Research
- Public RSS/Atom only, one request per configured feed per run.
- Local seed data is a fallback when public feeds return no usable items.
- Seed records are marked local_seed_data / seed_unverified and must not be treated as verified research.

## Ranking
Each opportunity receives:
- matched_keywords
- keyword_score
- intent_score
- opportunity_score
- research_quality

The ranking is deterministic and auditable: opportunity_score = keyword_score + intent_score.

## Content
Content is generated with deterministic templates. It does not claim first-hand experience and remains draft_requires_human_review.

## Validation
Validation checks source URL, review status, disclosure, outline presence, and unsupported experience claims.

## Decision
The decision engine records a traceable JSONL decision. Automatic publishing remains disabled.

## Zero-cost guard
The runtime requires budget_thb == 0 and no_payment_guard == true. Paid providers are not invoked.

## Failure isolation
A research provider failure is logged and the local seed fallback is attempted. A single failed feed does not abort the entire research pass.

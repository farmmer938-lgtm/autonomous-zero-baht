# Zero Bureaucracy KPI Framework (platform-ready)

A commercial, reusable framework that turns "bureaucracy elimination" into measurable,
configurable KPIs a B2B platform can embed as scoring logic and dashboards.
This is a **product asset**, not a consulting report.

## Contents
- `kpi-library.json` — the core library: 12 KPIs across 5 dimensions, each with
  definition, formula, unit, benchmark anchors (good/median/poor), data source,
  scoring rule, and per-client config knobs.
- `scoring.py` — reference implementation of the scoring logic (sub-score ->
  dimension score -> composite **ZB-Index** + grade).
- `sample_input.json` — example client snapshot.
- `test_scoring.py` — 7 pytest cases covering anchors, clamping, grade bands,
  full-snapshot shape, perfect-score bound, and per-client benchmark overrides.

## Dimensions
Speed · Effort · Automation · Duplication · Friction

## KPIs (12)
| ID | KPI | Dimension | Unit | Direction |
|----|-----|-----------|------|-----------|
| CT | Cycle Time | Speed | hours | lower |
| AL | Approval Latency | Speed | hours | lower |
| HD | Handoff Delay | Speed | hours | lower |
| TT | Touch Time | Effort | minutes | lower |
| FB | Form Burden | Effort | fields | lower |
| RR | Rework Rate | Effort | ratio | lower |
| AC | Automation Coverage | Automation | ratio | higher |
| STP | Straight-Through Processing | Automation | ratio | higher |
| DIS | Digital Intake Share | Automation | ratio | higher |
| DRR | Data Re-entry Rate | Duplication | ratio | lower |
| DAC | Duplicate Approval Count | Duplication | count | lower |
| CFI | Compliance Friction Index | Friction | controls/unit | lower |

## Scoring
Every KPI's raw value is converted to a 0-100 sub-score by a linear clamp between its
good and poor anchors (direction-aware). Dimension scores are weighted means of their
KPIs; the **ZB-Index** is the mean of dimension scores. Grades: A Frictionless (>=85),
B Lean (>=70), C Mixed (>=55), D Bureaucratic (>=40), E Gridlocked.

## Configurable per client
- `benchmark_overrides`: industry-specific good/poor anchors per KPI.
- `weights`: per-KPI and per-dimension weights (summing to 1).
- `excluded_kpis`: KPIs a client cannot instrument yet (dropped and re-normalized).

## Dashboard
Gauge (ZB-Index + bands), radar (5 dimensions), bar (worst KPIs first), weekly
timeseries (trend), and a KPI table. Refreshes nightly, or near-real-time if the
platform emits events.

## Monetization
Product tiers (Starter $49 / Pro $199 / Enterprise $999 per month), a metered
scoring API ($5 per 1,000 calls), and per-industry benchmark packs sold as add-ons.

## Run
    python3 scoring.py sample_input.json
    python3 -m pytest -q test_scoring.py

## Result
    ZB-Index: 57.94  (C — Mixed)   [sample snapshot]
    7 passed

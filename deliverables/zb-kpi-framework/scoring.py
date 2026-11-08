#!/usr/bin/env python3
"""Reference implementation of the Zero Bureaucracy KPI Framework scoring logic.

Loads kpi-library.json, computes a 0-100 sub-score per KPI from raw observations,
aggregates dimension scores, and produces the composite ZB-Index and grade.

Design: every KPI declares good/poor benchmark anchors and a direction. A sub-score
is a linear clamp between those anchors, so heterogeneous units (hours, ratios,
counts) compose into one comparable index.

Usage:
    python scoring.py sample_input.json            # score one client snapshot
    python scoring.py sample_input.json --json     # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = json.load(open(os.path.join(HERE, "kpi-library.json")))


def _clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def sub_score(value, good, poor, direction, overrides=None):
    """Linear clamp between the good and poor anchors, honoring direction."""
    if overrides:
        good = overrides.get("good", good)
        poor = overrides.get("poor", poor)
    if good == poor:
        return 100.0
    if direction == "lower_is_better":
        # value <= good -> 100 ; value >= poor -> 0
        s = (poor - value) / (poor - good) * 100.0
    else:
        # value >= good -> 100 ; value <= poor -> 0
        s = (value - poor) / (good - poor) * 100.0
    return round(_clamp(s), 2)


def grade_for(index):
    for band in LIB["scoring_logic"]["grade_bands"]:
        if index >= band["min"]:
            return band["grade"], band["label"]
    return "E", "Gridlocked"


def score_snapshot(observations, weights=None, benchmark_overrides=None):
    """observations: {kpi_id: value}. Returns sub-scores, dimension scores, ZB-Index.

    weights: {kpi_id: weight} (default 1.0 each). benchmark_overrides: {kpi_id: {good,poor}}.
    """
    weights = weights or {}
    benchmark_overrides = benchmark_overrides or {}
    subs = {}
    by_dim = {}
    for kpi in LIB["kpis"]:
        kid = kpi["id"]
        if kid not in observations:
            continue
        w = float(weights.get(kid, 1.0))
        s = sub_score(observations[kid], kpi["benchmark"]["good"], kpi["benchmark"]["poor"],
                      kpi["direction"], benchmark_overrides.get(kid))
        subs[kid] = {"value": observations[kid], "sub_score": s, "weight": w,
                     "name": kpi["name"], "dimension": kpi["dimension"], "unit": kpi["unit"]}
        by_dim.setdefault(kpi["dimension"], []).append((s, w))

    dim_scores = {}
    for dim, pairs in by_dim.items():
        tw = sum(w for _, w in pairs) or 1.0
        dim_scores[dim] = round(sum(s * w for s, w in pairs) / tw, 2)

    if dim_scores:
        index = round(sum(dim_scores.values()) / len(dim_scores), 2)
    else:
        index = 0.0
    g, label = grade_for(index)
    return {"zb_index": index, "grade": g, "grade_label": label,
            "dimension_scores": dim_scores, "kpi_scores": subs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", help="JSON file: {kpi_id: value} or {observations:{...}}")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    raw = json.load(open(a.observations))
    obs = raw.get("observations", raw) if isinstance(raw, dict) else raw
    result = score_snapshot(obs, raw.get("weights") if isinstance(raw, dict) else None,
                            raw.get("benchmark_overrides") if isinstance(raw, dict) else None)
    if a.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"ZB-Index: {result['zb_index']}  ({result['grade']} — {result['grade_label']})")
        for d, v in sorted(result["dimension_scores"].items()):
            print(f"  {d:<12} {v:>6}")
        print("  worst KPIs:")
        for kid, k in sorted(result["kpi_scores"].items(), key=lambda x: x[1]["sub_score"])[:5]:
            print(f"    {kid:<4} {k['name']:<26} {k['value']:>8} {k['unit']:<14} -> {k['sub_score']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

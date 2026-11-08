import json, os
from scoring import sub_score, score_snapshot, grade_for

def test_lower_is_better_anchors():
    assert sub_score(4, 4, 120, "lower_is_better") == 100.0
    assert sub_score(120, 4, 120, "lower_is_better") == 0.0
    assert 0 < sub_score(62, 4, 120, "lower_is_better") < 100

def test_higher_is_better_anchors():
    assert sub_score(0.85, 0.85, 0.15, "higher_is_better") == 100.0
    assert sub_score(0.15, 0.85, 0.15, "higher_is_better") == 0.0

def test_clamped_beyond_anchors():
    assert sub_score(0, 4, 120, "lower_is_better") == 100.0
    assert sub_score(999, 4, 120, "lower_is_better") == 0.0

def test_grade_bands():
    assert grade_for(90)[0] == "A"
    assert grade_for(72)[0] == "B"
    assert grade_for(10)[0] == "E"

def test_full_snapshot_shape():
    r = score_snapshot(json.load(open("sample_input.json"))["observations"])
    assert 0 <= r["zb_index"] <= 100
    assert set(r["dimension_scores"]) <= {"speed","effort","automation","duplication","friction"}
    assert len(r["kpi_scores"]) == 12

def test_perfect_and_worst_bounds():
    best = {k["id"]: k["benchmark"]["good"] for k in json.load(open("kpi-library.json"))["kpis"]}
    r = score_snapshot(best)
    assert r["zb_index"] == 100.0 and r["grade"] == "A"

def test_benchmark_overrides_change_score():
    base = score_snapshot({"CT": 30})
    over = score_snapshot({"CT": 30}, benchmark_overrides={"CT": {"good": 60, "poor": 120}})
    assert over["kpi_scores"]["CT"]["sub_score"] > base["kpi_scores"]["CT"]["sub_score"]

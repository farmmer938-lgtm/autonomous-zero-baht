import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from conv import csv_to_json, json_to_csv


def test_union_of_keys_and_missing_fill():
    rows = [{"a": 1, "b": 2}, {"a": 3, "c": 4}]
    out = json_to_csv(rows)
    lines = out.strip().splitlines()
    assert lines[0] == "a,b,c"
    assert lines[1] == "1,2,"
    assert lines[2] == "3,,4"


def test_none_and_nested_become_strings():
    out = json_to_csv([{"a": None, "b": {"x": 1}, "c": [1, 2]}])
    assert out.strip().splitlines()[1] == ',"{""x"": 1}","[1, 2]"'


def test_roundtrip():
    rows = [{"a": "1", "b": "2"}, {"a": "3", "b": ""}]
    assert csv_to_json(json_to_csv(rows)) == rows


def test_rejects_non_array():
    try:
        json_to_csv({"a": 1})
    except ValueError as e:
        assert "array" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_explicit_columns():
    out = json_to_csv([{"a": 1, "b": 2}], columns=["b"])
    assert out.strip().splitlines() == ["b", "2"]

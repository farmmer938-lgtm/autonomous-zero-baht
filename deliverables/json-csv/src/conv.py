"""Flat JSON <-> CSV converter.

Reads a JSON array of flat objects and writes CSV, or the reverse. Missing keys
become empty fields; extra keys are dropped on the CSV->JSON path unless the CSV
has no rows to infer a schema from.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path


def json_to_csv(rows, columns=None):
    if not isinstance(rows, list):
        raise ValueError("input must be a JSON array")
    if columns is None:
        columns = []
        seen = set()
        for r in rows:
            if not isinstance(r, dict):
                raise ValueError("every element must be an object")
            for k in r:
                if k not in seen:
                    seen.add(k)
                    columns.append(k)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, restval="", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: _cell(r.get(k)) for k in columns})
    return buf.getvalue()


def csv_to_json(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    return [dict(r) for r in rows]


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def main(argv=None):
    p = argparse.ArgumentParser(description="Convert flat JSON to CSV (or back).")
    p.add_argument("infile")
    p.add_argument("outfile")
    p.add_argument("--reverse", action="store_true", help="CSV -> JSON")
    a = p.parse_args(argv)
    src = Path(a.infile).read_text(encoding="utf-8")
    if a.reverse:
        out = json.dumps(csv_to_json(src), ensure_ascii=False, indent=2)
    else:
        out = json_to_csv(json.loads(src))
    Path(a.outfile).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

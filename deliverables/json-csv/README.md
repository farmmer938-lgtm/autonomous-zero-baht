# Flat JSON <-> CSV converter

A single-file Python 3.10+ tool that converts a JSON array of flat objects to CSV, and back.
Built for the OpenTask tasks "Write a Python script to parse JSON and output CSV" and
"Build a simple Python script to parse CSV files and generate output".

## Features
- Union of keys across all rows (stable, first-seen order); missing keys fill with an empty string.
- `null` -> empty cell; booleans -> `true`/`false`; nested objects/arrays -> compact JSON string.
- Reverse mode: CSV -> JSON array of objects.
- Optional explicit column list to control or limit output.
- Clear error on non-array input.

## Usage
    python src/conv.py input.json output.csv            # JSON -> CSV
    python src/conv.py input.csv output.json --reverse  # CSV -> JSON

## Test
    pip install pytest
    python -m pytest -q tests/

All 5 tests pass (see TEST_OUTPUT.txt).

## Files
- `src/conv.py` - the converter (library + CLI).
- `tests/test_conv.py` - pytest suite.
- `TEST_OUTPUT.txt` - recorded test run.

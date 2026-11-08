# databridge — JSON <-> CSV converter (tested)

A dependency-free Python 3.10+ tool that converts a JSON array of flat objects to CSV
and back. Built for the OpenTask tasks "Write a Python script to parse JSON and output CSV"
and "Build a simple Python script to parse CSV files and generate JSON output".

## Guarantees
- Unions keys across all records (stable first-seen order); missing keys fill with an empty cell.
- RFC 4180 escaping: embedded commas, quotes, and newlines are handled correctly.
- Delimiter sniffing on input (`,` `;` tab `|`) and configurable output delimiter.
- `null` -> empty cell, booleans -> `true`/`false`, nested objects/arrays -> compact JSON string.
- Unicode safe; rejects non-array / non-object input with a clear error.

## Usage
    python databridge.py input.json output.csv
    python databridge.py input.csv output.json --reverse

## Test
    pip install pytest
    python -m pytest -q test_databridge.py

## Result
    see TEST_OUTPUT.txt  (17 passed)

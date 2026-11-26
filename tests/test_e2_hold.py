"""The hold recorder may not invent a visitor, and may not lose the day-30 decision date."""
import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_e2_hold as hold  # noqa: E402


class FakeChecker:
    def __init__(self, status=200):
        self.status = status

    def head(self, url, timeout=15):
        return self.status


class HoldRecordTests(unittest.TestCase):
    def test_a_200_is_recorded_as_availability_not_as_a_visit(self):
        row = hold.record(now=datetime(2026, 11, 25, 17, 0, tzinfo=timezone.utc),
                          checker=FakeChecker(200))
        self.assertIsNone(row["visits"])
        self.assertIsNone(row["discovery"]["search_console"])
        self.assertEqual(row["enquiries"]["genuine"], 0)
        self.assertEqual(row["paid_usdc"], 0.0)
        self.assertIn("not counted as visitors", row["note"])

    def test_a_dead_page_lowers_the_count_instead_of_being_ignored(self):
        row = hold.record(now=datetime(2026, 11, 25, tzinfo=timezone.utc),
                          checker=FakeChecker(404))
        self.assertEqual(row["pages_200"], 0)
        self.assertEqual(row["paths_checked"], len(__import__("af_publish_check").PATHS))

    def test_decision_date_and_day_counter_are_fixed(self):
        row = hold.record(now=datetime(2026, 12, 1, tzinfo=timezone.utc), checker=FakeChecker())
        self.assertEqual(row["decision_date"], "2026-12-25")
        self.assertEqual(row["day_of_hold"], 6)

    def test_log_is_append_only_jsonl(self):
        tmp = Path("/tmp/e2_hold_test.jsonl")
        tmp.unlink(missing_ok=True)
        hold.append({"at": "a"}, path=tmp)
        hold.append({"at": "b"}, path=tmp)
        self.assertEqual([json.loads(l)["at"] for l in tmp.read_text().splitlines()], ["a", "b"])
        tmp.unlink()

    def test_status_counts_down_to_the_decision(self):
        st = hold.status(path=Path("/tmp/none.jsonl"), today=date(2026, 12, 20))
        self.assertEqual(st["days_left"], 5)
        self.assertEqual(st["checks"], 0)
        self.assertIsNone(st["latest"])


if __name__ == "__main__":
    unittest.main()

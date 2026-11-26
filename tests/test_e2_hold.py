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


class EvidenceIntegrityTests(unittest.TestCase):
    def test_pii_is_refused(self):
        for bad in ({"contact": "someone@example.com"},
                    {"phone": "0812345678"},
                    {"pay": "PromptPay 0899999999"},
                    {"key": "0x" + "a" * 64},
                    {"note": "seed phrase attached"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                hold.assert_no_pii(bad)

    def test_ordinary_record_passes_the_pii_guard(self):
        row = hold.record(now=datetime(2026, 11, 26, tzinfo=timezone.utc), checker=FakeChecker())
        self.assertEqual(hold.assert_no_pii(row), row)

    def test_null_is_not_zero(self):
        row = hold.record(now=datetime(2026, 11, 26, tzinfo=timezone.utc), checker=FakeChecker())
        self.assertIsNone(row["visits"])
        self.assertIsNone(row["discovery"]["search_console"])
        self.assertEqual(row["discovery"]["referrals"], None)
        self.assertIn("null means 'not measured'", row["note"])

    def test_three_counts_are_reported_separately(self):
        row = hold.record(now=datetime(2026, 11, 26, tzinfo=timezone.utc), checker=FakeChecker())
        c = row["counts"]
        self.assertEqual(c["e2_paths_checked"], 1)          # only audit/e2/ is in PATHS
        self.assertEqual(c["panel_pages_expected"], 11)     # 10 token pages + index
        self.assertNotIn("total_pages", c)                  # no number that invites double counting

    def test_verify_log_flags_a_tampered_order(self):
        tmp = Path("/tmp/e2_hold_verify.jsonl")
        tmp.write_text('{"at":"2026-12-01T00:00:00+00:00"}\n{"at":"2026-11-01T00:00:00+00:00"}\n',
                       encoding="utf-8")
        res = hold.verify_log(tmp)
        self.assertFalse(res["ok"])
        self.assertTrue(any("monotonic" in p for p in res["problems"]))
        tmp.unlink()

    def test_verify_log_flags_pii_that_got_in(self):
        tmp = Path("/tmp/e2_hold_pii.jsonl")
        tmp.write_text('{"at":"2026-12-01T00:00:00+00:00","who":"a@b.co"}\n', encoding="utf-8")
        res = hold.verify_log(tmp)
        self.assertFalse(res["ok"])
        tmp.unlink()

    def test_no_workflow_runs_the_recorder_so_the_mode_is_on_demand(self):
        """If someone wires a cron, this test flips and the report must change with it."""
        row = hold.record(now=datetime(2026, 11, 26, tzinfo=timezone.utc), checker=FakeChecker())
        self.assertEqual(row["measurement"]["mode"].startswith("on-demand"), not hold.scheduled())

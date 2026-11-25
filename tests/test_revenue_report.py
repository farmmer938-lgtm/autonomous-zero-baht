"""H5/H6: the report must under-claim, never over-claim.

The ledger written before the strict matcher has rows marked `confirmed: True` with no
`orderKey`, so a naive sum would report 0.1 USDC of "cash" that no order explains. The
report sums only confirmed rows that carry an order key and a tx hash.
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_revenue_report as rr  # noqa: E402

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


class AgeTests(unittest.TestCase):
    def test_z_suffix_is_parsed(self):
        self.assertAlmostEqual(rr.age_hours("2026-11-25T09:00:00Z", NOW), 3.0)

    def test_offset_is_parsed(self):
        self.assertAlmostEqual(rr.age_hours("2026-11-25T09:00:00+00:00", NOW), 3.0)

    def test_naive_stamp_is_treated_as_utc(self):
        self.assertAlmostEqual(rr.age_hours("2026-11-25T09:00:00", NOW), 3.0)

    def test_garbage_is_none_not_zero(self):
        self.assertIsNone(rr.age_hours("not a date", NOW))


class CashTests(unittest.TestCase):
    def test_only_confirmed_ordered_rows_count(self):
        paid = {"payments": [
            {"amount_usdc": 5.0, "confirmed": True, "orderKey": "k", "txHash": "0x1"},
            {"amount_usdc": 0.1, "confirmed": True},                      # legacy, no order
            {"amount_usdc": 9.0, "confirmed": False, "orderKey": "k2", "txHash": "0x2"},
            {"amount_usdc": 2.0, "confirmed": True, "orderKey": "k3"},     # no tx named
        ]}
        cash, rows = rr.cash_from_paid_index(paid)
        self.assertEqual(cash, 5.0)
        self.assertEqual(rows, 1)

    def test_an_empty_index_is_zero(self):
        self.assertEqual(rr.cash_from_paid_index({}), (0.0, 0))

    def test_pending_rows_are_separated(self):
        ledger = {"payments": [{"confirmed": True}, {"confirmed": False}]}
        self.assertEqual(len(rr.pending_from_ledger(ledger)), 1)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.saved = {k: getattr(rr, k) for k in
                      ("MANIFEST", "WATCH", "OPP", "PAID", "LEDGER", "CHAIN")}

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(rr, k, v)
        self.tmp.cleanup()

    def write(self, name, obj):
        p = self.dir / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return str(p)

    def test_a_four_hour_old_manifest_is_stale(self):
        rr.MANIFEST = self.write("m.json", {"updated_at": "2026-11-25T08:00:00+00:00",
                                            "public_base": "https://x"})
        m = rr.monitor(NOW)
        self.assertAlmostEqual(m["manifest_age_hours"], 4.0)
        self.assertTrue(m["manifest_stale"])

    def test_a_fresh_manifest_is_not_stale(self):
        rr.MANIFEST = self.write("m.json", {"updated_at": "2026-11-25T11:30:00+00:00"})
        self.assertFalse(rr.monitor(NOW)["manifest_stale"])

    def test_a_missing_manifest_counts_as_stale(self):
        rr.MANIFEST = str(self.dir / "absent.json")
        self.assertTrue(rr.monitor(NOW)["manifest_stale"])

    def test_failed_workflow_runs_are_reported(self):
        rr.MANIFEST = str(self.dir / "absent.json")
        rr.WATCH = self.write("w.json", {"healthy": True, "fail": [], "warn": []})
        health = self.dir / "data" / "workflow_health.json"
        health.parent.mkdir()
        health.write_text(json.dumps({"runs": [
            {"workflow": "a", "at": "t", "failed": []},
            {"workflow": "b", "at": "t", "failed": ["unit-tests"]}]}), encoding="utf-8")
        cwd = Path.cwd()
        try:
            import os
            os.chdir(self.dir)
            m = rr.monitor(NOW)
        finally:
            os.chdir(cwd)
        self.assertEqual(m["workflow_runs_failed"], 1)


class ReportShapeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.saved = {k: getattr(rr, k) for k in
                      ("MANIFEST", "WATCH", "OPP", "PAID", "LEDGER", "CHAIN")}
        for name, obj in {
            "m.json": {"updated_at": "2026-11-25T11:30:00+00:00", "public_base": "https://x"},
            "w.json": {"healthy": True, "fail": [], "warn": ["stale manifest"]},
            "o.json": {"checked_at": "now", "opportunities": [
                {"id": "frantic:97", "verdict": "loss", "net_usd": 0},
                {"id": "x", "verdict": "needs_owner", "title": "t", "reasons": ["identity"]}],
                "rails_not_counted": [{"rail": "x402", "status": "PARKED"}]},
            "p.json": {"payments": []},
            "l.json": {"payments": []},
            "c.json": {"verdict": "CONTINUOUS", "inbound_usdc_total": 0.1},
        }.items():
            (self.dir / name).write_text(json.dumps(obj), encoding="utf-8")
        rr.MANIFEST = str(self.dir / "m.json")
        rr.WATCH = str(self.dir / "w.json")
        rr.OPP = str(self.dir / "o.json")
        rr.PAID = str(self.dir / "p.json")
        rr.LEDGER = str(self.dir / "l.json")
        rr.CHAIN = str(self.dir / "c.json")

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(rr, k, v)
        self.tmp.cleanup()

    def test_zero_cash_is_stated_as_zero(self):
        r = rr.build_report(NOW)
        self.assertEqual(r["headline"]["cash_received_usdc"], 0.0)
        self.assertEqual(r["headline"]["act_now_opportunities"], 0)

    def test_needs_owner_is_surfaced(self):
        self.assertEqual(rr.build_report(NOW)["headline"]["needs_owner"], 1)

    def test_the_markdown_says_nothing_payable_when_nothing_is(self):
        md = rr.render_md(rr.build_report(NOW))
        self.assertIn("nothing payable today", md)

    def test_a_fresh_manifest_is_not_marked_stale(self):
        md = rr.render_md(rr.build_report(NOW))
        self.assertIn("0.5h old", md)
        self.assertNotIn("**STALE**", md)

    def test_a_stale_manifest_is_marked_in_the_markdown(self):
        (self.dir / "m.json").write_text(json.dumps(
            {"updated_at": "2026-11-25T00:00:00+00:00", "public_base": "https://x"}),
            encoding="utf-8")
        self.assertIn("**STALE**", rr.render_md(rr.build_report(NOW)))

    def test_costs_default_to_zero(self):
        self.assertEqual(rr.build_report(NOW)["costs"]["usd"], 0.0)


if __name__ == "__main__":
    unittest.main()

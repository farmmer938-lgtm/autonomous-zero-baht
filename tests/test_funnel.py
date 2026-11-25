"""Eight stages, none of them inferred from another, and reach never invented."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_funnel as fn  # noqa: E402

ISSUES = [
    {"number": 1, "labels": [{"name": "audit-request"}], "createdAt": "t1",
     "comments": [{"author": {"login": "someone"}}]},
    {"number": 2, "labels": [{"name": "bug"}], "createdAt": "t2"},
    {"number": 75, "labels": [{"name": "audit-request"}, {"name": "self-test"}],
     "createdAt": "t3", "comments": [{"author": {"login": "someone"}}]},
]
ORDERS = [{"issue": 1, "status": "delivered_unpaid"},
          {"issue": 75, "status": "delivered_unpaid"},
          {"issue": 9, "status": "failed"}]
PAID = {"payments": [
    {"amount_usdc": 0.5, "confirmed": True, "orderKey": "micro:x:0.500", "txHash": "0x1"},
    {"amount_usdc": 0.5, "confirmed": True, "orderKey": "micro:x:0.500", "txHash": "0x1"},
    {"amount_usdc": 9.0, "confirmed": False, "orderKey": "k", "txHash": "0x2"},
]}
PUBLISHED = {"published": 7, "note": "200 only"}


def run(**over):
    kw = {"issue_rows": ISSUES, "order_rows": ORDERS, "paid": PAID, "published": PUBLISHED}
    kw.update(over)
    f = fn.compute(kw["issue_rows"], kw["order_rows"], kw["paid"], kw["published"])
    return f


class StageTests(unittest.TestCase):
    def test_every_stage_is_present(self):
        f = run()
        for s in fn.STAGES:
            self.assertIn(s, f)

    def test_reach_is_always_null(self):
        self.assertIsNone(run()["reach"])
        self.assertIsNone(run(published={})["reach"])

    def test_publication_is_not_reach(self):
        f = run(published={"published": 99})
        self.assertEqual(f["published"], 99)
        self.assertIsNone(f["reach"])

    def test_only_audit_requests_without_self_test_are_qualified(self):
        self.assertEqual(run()["qualified_interest"], 1)

    def test_engagement_counts_strangers_only(self):
        issues = [{"number": 3, "labels": [{"name": "audit-request"}],
                   "comments": [{"author": {"login": "github-actions[bot]"}}]}]
        self.assertIsNone(run(issue_rows=issues)["engagement"])
        self.assertEqual(run()["engagement"], 1)

    def test_af_own_self_test_is_removed_everywhere(self):
        f = run()
        self.assertEqual(f["excluded_self_tests"], [75])
        self.assertEqual(f["delivered"], 1)
        self.assertEqual(f["orders"], 2)  # issues 1 and 9

    def test_a_self_test_order_is_dropped_even_without_the_issue_list(self):
        f = run(issue_rows=[], order_rows=[{"issue": 75, "status": "delivered_unpaid",
                                           "self_test": True}])
        self.assertEqual((f["orders"], f["delivered"]), (0, 0))

    def test_unasked_orders_are_named(self):
        self.assertEqual(run()["unasked_orders"], [9])

    def test_duplicate_payments_are_collapsed(self):
        self.assertEqual(run()["paid"], 1)
        self.assertEqual(run()["cash_usdc"], 0.5)

    def test_net_revenue_is_cash_minus_costs(self):
        self.assertEqual(run()["net_revenue"], 0.5)

    def test_delivery_is_not_a_sale(self):
        f = run(paid={})
        self.assertEqual(f["delivered"], 1)
        self.assertEqual((f["paid"], f["net_revenue"]), (0, 0.0))

    def test_a_page_is_not_an_audience(self):
        # 0 interest out of 7 published pages is a real measurement (0.0), unlike reach,
        # which stays null because nobody is counting readers.
        f = run(issue_rows=[], published={"published": 7})
        self.assertEqual(f["conversion"]["published_to_interest"], 0.0)
        self.assertIsNone(f["reach"])
        self.assertEqual(f["qualified_interest"], 0)


class OrderDedupTests(unittest.TestCase):
    def test_two_files_for_one_issue_keep_the_latest(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        d = Path(tmp.name)
        (d / "1.json").write_text(json.dumps({"issue": 1, "status": "failed"}))
        (d / "1b.json").write_text(json.dumps({"issue": 1, "status": "delivered_unpaid"}))
        real = fn.ORDERS
        fn.ORDERS = d
        try:
            self.assertEqual(len(fn.orders()), 1)
            self.assertEqual(fn.orders()[0]["status"], "delivered_unpaid")
        finally:
            fn.ORDERS = real
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

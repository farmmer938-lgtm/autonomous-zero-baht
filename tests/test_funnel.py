"""The funnel must not invent a stage. Visitors are unknown, delivery is not revenue."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_funnel as fn  # noqa: E402

ISSUES = [
    {"number": 1, "labels": [{"name": "audit-request"}], "createdAt": "t1"},
    {"number": 2, "labels": [{"name": "bug"}], "createdAt": "t2"},
    {"number": 3, "labels": [], "createdAt": "t3"},
]
ORDERS = [{"status": "delivered_unpaid"}, {"status": "failed"}]
PAID = {"payments": [
    {"amount_usdc": 0.5, "confirmed": True, "orderKey": "micro:x:0.500", "txHash": "0x1"},
    {"amount_usdc": 9.0, "confirmed": False, "orderKey": "k", "txHash": "0x2"},
]}


class FunnelTests(unittest.TestCase):
    def test_visitors_are_null_not_zero(self):
        f = fn.compute(ISSUES, ORDERS, PAID)
        self.assertIsNone(f["visitors"])
        self.assertIn("unknown", f["visitors_note"])

    def test_only_audit_requests_count_as_interest(self):
        self.assertEqual(fn.compute(ISSUES, ORDERS, PAID)["interest"], 1)

    def test_delivery_and_failure_are_counted_apart(self):
        f = fn.compute(ISSUES, ORDERS, PAID)
        self.assertEqual((f["delivered"], f["failed"]), (1, 1))

    def test_only_confirmed_payments_are_cash(self):
        f = fn.compute(ISSUES, ORDERS, PAID)
        self.assertEqual((f["paid_orders"], f["cash_usdc"]), (1, 0.5))

    def test_conversion_is_none_when_nothing_happened(self):
        f = fn.compute([], [], {})
        self.assertIsNone(f["conversion"]["interest_to_delivered"])
        self.assertIsNone(f["conversion"]["delivered_to_paid"])

    def test_af_own_self_test_is_not_a_customer(self):
        issues = ISSUES + [{"number": 75, "labels": [{"name": "audit-request"},
                                                     {"name": "self-test"}],
                            "createdAt": "t4"}]
        orders = ORDERS + [{"status": "delivered_unpaid", "issue": 75}]
        f = fn.compute(issues, orders, PAID)
        self.assertEqual(f["interest"], 1)
        self.assertEqual(f["delivered"], 1)
        self.assertEqual(f["excluded_self_tests"], [75])

    def test_a_delivery_is_not_a_sale(self):
        f = fn.compute(ISSUES, ORDERS, {})
        self.assertEqual(f["delivered"], 1)
        self.assertEqual(f["paid_orders"], 0)
        self.assertEqual(f["cash_usdc"], 0)


if __name__ == "__main__":
    unittest.main()

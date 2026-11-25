"""Phase F: the order index and the payment target are checked on their own.

A dead cashier must not hide a broken order file, and a stale file is a warning while an
unpayable one is a failure. WARN and FAIL are kept apart so the alert issue stays readable.
"""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.public_watch import (  # noqa: E402
    ORDERS_MAX_AGE_H, orders_state, payment_target_state)

WALLET = "0xf3C99a6d6e7C6b2ae00b44cC42cC3eb7691D7702"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def index(**kw):
    base = {"schema": "af.api.orders.v1", "pay_to": WALLET,
            "generatedAt": (NOW - timedelta(hours=1)).isoformat(), "orders": []}
    base.update(kw)
    return base


class OrdersStateTests(unittest.TestCase):
    def test_a_fresh_index_is_ok(self):
        state, note = orders_state(index(), now=NOW)
        self.assertEqual(state, "ok", note)

    def test_an_old_index_is_a_warning_not_a_failure(self):
        old = (NOW - timedelta(hours=ORDERS_MAX_AGE_H + 1)).isoformat()
        state, note = orders_state(index(generatedAt=old), now=NOW)
        self.assertEqual(state, "warn", note)
        self.assertIn("old", note)

    def test_a_missing_index_fails(self):
        self.assertEqual(orders_state(None, now=NOW)[0], "fail")

    def test_a_wrong_schema_fails(self):
        self.assertEqual(orders_state(index(schema="other"), now=NOW)[0], "fail")

    def test_a_missing_pay_to_fails(self):
        self.assertEqual(orders_state(index(pay_to=""), now=NOW)[0], "fail")

    def test_a_malformed_timestamp_warns(self):
        self.assertEqual(orders_state(index(generatedAt="yesterday"), now=NOW)[0], "warn")

    def test_the_order_count_is_reported(self):
        state, note = orders_state(index(orders=[{"id": "a"}]), now=NOW)
        self.assertEqual(state, "ok")
        self.assertIn("1 order", note)


class PaymentTargetTests(unittest.TestCase):
    def test_the_same_wallet_is_ok(self):
        state, note = payment_target_state(index(), {"wallet": WALLET})
        self.assertEqual(state, "ok", note)

    def test_a_different_wallet_fails(self):
        state, note = payment_target_state(index(), {"wallet": "0x" + "1" * 40})
        self.assertEqual(state, "fail")
        self.assertIn("revenue is read from", note)

    def test_case_is_ignored(self):
        self.assertEqual(payment_target_state(index(), {"wallet": WALLET.lower()})[0], "ok")

    def test_unknown_inputs_warn_instead_of_failing(self):
        self.assertEqual(payment_target_state(None, {})[0], "warn")


if __name__ == "__main__":
    unittest.main()

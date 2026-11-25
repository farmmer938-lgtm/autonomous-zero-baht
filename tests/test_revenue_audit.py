"""Phase B: money only becomes revenue when it is a third party AND an order names it.

`af_revenue_verify.py` used to add up every inbound USDC transfer, so AF paying its own
wallet made the verdict "CONTINUOUS" with 0.1 USDC of "income". These tests pin the
three-way split that replaced it.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_revenue_verify as rv  # noqa: E402

OWN = "0xf3c99a6d6e7c6b2ae00b44dc42cc3eb7691d7702"
CUSTOMER = "0xf007e34bd68feb0da9005b26b2456699d2432303"
SELF_SET = frozenset({OWN})


def rec(tx, sender, usdc, at="2026-11-20T00:00:00+00:00"):
    return {"tx": tx, "from": sender, "usdc": usdc, "at": at}


class ClassifyTests(unittest.TestCase):
    def test_a_transfer_from_af_own_wallet_is_a_self_transfer(self):
        self.assertEqual(rv.classify_transfer(OWN.upper(), SELF_SET), "self")

    def test_a_transfer_from_anyone_else_is_external(self):
        self.assertEqual(rv.classify_transfer(CUSTOMER, SELF_SET), "external")

    def test_a_transfer_with_no_sender_is_never_treated_as_self(self):
        self.assertEqual(rv.classify_transfer(None, SELF_SET), "external")

    def test_the_default_self_set_is_af_wallet(self):
        self.assertIn(OWN, rv.self_addresses())


class SplitTests(unittest.TestCase):
    def test_self_transfer_is_not_revenue(self):
        totals, rows = rv.summarise([rec("0xaa", OWN, 0.1)], SELF_SET, {})
        self.assertEqual(totals["customer_verified_usdc"], 0.0)
        self.assertEqual(totals["self_transfer_usdc"], 0.1)
        self.assertEqual(rows[0]["bucket"], "self_transfer_usdc")

    def test_an_external_payment_without_an_order_is_unattributed(self):
        totals, rows = rv.summarise([rec("0xbb", CUSTOMER, 0.000038)], SELF_SET, {})
        self.assertEqual(totals["customer_verified_usdc"], 0.0)
        self.assertEqual(totals["unattributed_usdc"], 0.000038)
        self.assertEqual(rows[0]["order_id"], None)

    def test_an_external_payment_named_by_an_order_is_verified_revenue(self):
        totals, rows = rv.summarise([rec("0xcc", CUSTOMER, 0.1)], SELF_SET, {"0xcc": "ord-1"})
        self.assertEqual(totals["customer_verified_usdc"], 0.1)
        self.assertEqual(rows[0]["order_id"], "ord-1")

    def test_an_order_id_cannot_promote_a_self_transfer(self):
        totals, _ = rv.summarise([rec("0xdd", OWN, 5.0)], SELF_SET, {"0xdd": "ord-2"})
        self.assertEqual(totals["customer_verified_usdc"], 0.0)
        self.assertEqual(totals["self_transfer_usdc"], 5.0)

    def test_tx_matching_is_case_insensitive(self):
        totals, _ = rv.summarise([rec("0xEE", CUSTOMER, 0.1)], SELF_SET, {"0xee": "ord-3"})
        self.assertEqual(totals["customer_verified_usdc"], 0.1)


class OwnTradeTests(unittest.TestCase):
    def test_a_cow_settlement_payment_is_own_trade_proceeds(self):
        cow = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
        self.assertEqual(rv.classify_transfer(cow, SELF_SET), "swap")

    def test_a_receipt_flagged_swap_is_not_revenue(self):
        rec_swap = dict(rec("0xff", CUSTOMER, 3.0), own_trade=True)
        totals, rows = rv.summarise([rec_swap], SELF_SET, {})
        self.assertEqual(totals["own_trade_usdc"], 3.0)
        self.assertEqual(totals["customer_verified_usdc"], 0.0)
        self.assertEqual(rows[0]["bucket"], "own_trade_usdc")

    def test_a_swap_flag_cannot_promote_a_self_transfer(self):
        rec_self = dict(rec("0x1f", OWN, 2.0), own_trade=True)
        totals, _ = rv.summarise([rec_self], SELF_SET, {})
        self.assertEqual(totals["self_transfer_usdc"], 2.0)
        self.assertEqual(totals["own_trade_usdc"], 0.0)

    def test_the_buckets_add_up_to_the_total_inbound(self):
        records = [rec("0xa1", OWN, 0.1), rec("0xa2", CUSTOMER, 0.05),
                   dict(rec("0xa3", CUSTOMER, 3.0), own_trade=True)]
        totals, _ = rv.summarise(records, SELF_SET, {"0xa2": "ord-9"})
        self.assertAlmostEqual(sum(totals.values()), 3.15, places=6)


class VerdictTests(unittest.TestCase):
    def test_no_third_party_transfer_is_none(self):
        self.assertEqual(rv.verdict(0, 0), "NONE")

    def test_one_third_party_transfer_is_first(self):
        self.assertEqual(rv.verdict(1, 1), "FIRST")

    def test_two_transfers_on_one_day_are_not_continuous(self):
        self.assertEqual(rv.verdict(2, 1), "RECURRING_SAME_DAY")

    def test_two_transfers_on_two_days_are_continuous(self):
        self.assertEqual(rv.verdict(2, 2), "CONTINUOUS")


class RealLedgerTests(unittest.TestCase):
    """The published ledger must not read as revenue: 0.1 USDC of it is AF's own money."""

    def setUp(self):
        ledger = json.loads(Path("data/revenue_ledger.json").read_text(encoding="utf-8"))
        records = [dict(v, tx=k) for k, v in ledger["first_seen"].items()]
        self.totals, self.rows = rv.summarise(records, rv.self_addresses(), rv.load_order_txs())

    def test_no_customer_revenue_is_verified(self):
        self.assertEqual(self.totals["customer_verified_usdc"], 0.0)

    def test_the_self_transfer_is_reported_as_self_transfer(self):
        self.assertGreater(self.totals["self_transfer_usdc"], 0.0)

    def test_no_transfer_is_linked_to_an_order_yet(self):
        self.assertTrue(all(r["order_id"] is None for r in self.rows))


if __name__ == "__main__":
    unittest.main()

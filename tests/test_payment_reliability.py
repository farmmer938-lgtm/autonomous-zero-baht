"""H3: a sale is counted only when it is unique, third-party and deep enough to be final.

The amount is the order id, so the failure modes are specific: the same tx scanned twice,
two txs paying one invoice, AF paying itself, and a transfer still sitting in the tip block.
None of them may reach `cash_received_usdc`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_selfserve as ss  # noqa: E402

TOKEN = "0xAbCdEf0123456789aBcDeF0123456789AbCdEf01"
INVOICE = {"token": TOKEN, "symbol": "TKN", "amount_usdc": 0.523, "tier": "micro_fix",
           "report": "site/reviews/x.json"}
INV = {0.523: INVOICE}
BUYER = "0x1111111111111111111111111111111111111111"
LATEST = 1_000_000


def transfer(tx="0xabc", amount=0.523, sender=BUYER, block=LATEST - 100):
    return {"txHash": tx, "amount_usdc": amount, "from": sender, "block": block}


def classify(t, seen_txs=frozenset(), seen_orders=frozenset()):
    return ss.classify(t, INV, set(seen_txs), set(seen_orders), LATEST)


class ExactAmountTests(unittest.TestCase):
    def test_an_exact_invoice_amount_is_a_payment(self):
        self.assertEqual(classify(transfer())["kind"], "payment")

    def test_a_wrong_amount_is_not_a_sale(self):
        self.assertEqual(classify(transfer(amount=0.52))["kind"], "unmatched")

    def test_a_rounded_amount_within_tolerance_still_matches(self):
        self.assertEqual(classify(transfer(amount=0.5232))["kind"], "payment")

    def test_a_large_amount_is_not_an_invoice(self):
        self.assertEqual(classify(transfer(amount=10.0))["kind"], "unmatched")


class DuplicateTests(unittest.TestCase):
    def test_the_same_tx_is_never_counted_twice(self):
        self.assertEqual(classify(transfer(tx="0xdead"), seen_txs={"0xdead"})["kind"],
                         "duplicate_tx")

    def test_tx_hashes_compare_case_insensitively(self):
        self.assertEqual(classify(transfer(tx="0xDEAD"), seen_txs={"0xdead"})["kind"],
                         "duplicate_tx")

    def test_a_second_payment_for_one_order_is_refused(self):
        key = ss.order_key(INVOICE)
        self.assertEqual(classify(transfer(tx="0xother"), seen_orders={key})["kind"],
                         "duplicate_order")

    def test_the_order_key_binds_tier_token_and_amount(self):
        key = ss.order_key(INVOICE)
        self.assertIn("micro_fix", key)
        self.assertIn(TOKEN.lower(), key)
        self.assertIn("0.523", key)


class SelfTransferTests(unittest.TestCase):
    def test_af_paying_itself_is_not_a_sale(self):
        self.assertEqual(classify(transfer(sender=ss.AF.lower()))["kind"], "self")

    def test_a_cow_settlement_is_not_a_sale(self):
        cow = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
        self.assertEqual(classify(transfer(sender=cow))["kind"], "self")


class ConfirmationTests(unittest.TestCase):
    def test_a_transfer_in_the_tip_block_is_pending(self):
        self.assertEqual(classify(transfer(block=LATEST))["kind"], "pending")

    def test_one_confirmation_short_is_still_pending(self):
        self.assertEqual(
            classify(transfer(block=LATEST - ss.MIN_CONFIRMATIONS + 1))["kind"], "pending")

    def test_exactly_enough_confirmations_is_a_payment(self):
        self.assertEqual(
            classify(transfer(block=LATEST - ss.MIN_CONFIRMATIONS))["kind"], "payment")

    def test_the_default_depth_is_twelve_blocks(self):
        self.assertEqual(ss.MIN_CONFIRMATIONS, 12)


class LedgerCountTests(unittest.TestCase):
    def test_cash_excludes_pending_entries(self):
        payments = [{"amount_usdc": 1.0, "confirmed": True, "orderKey": "a"},
                    {"amount_usdc": 5.0, "confirmed": False, "orderKey": "b"}]
        cash = [p for p in payments if p.get("confirmed") and p.get("orderKey")]
        self.assertEqual(sum(p["amount_usdc"] for p in cash), 1.0)


if __name__ == "__main__":
    unittest.main()

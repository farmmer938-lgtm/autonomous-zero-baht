import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from af_selfserve import assign_amounts, invoice_map, invoices, micro_invoices
from af_service import PRICE_USD, reconcile

TX_A = "0x" + "a" * 64
TX_B = "0x" + "b" * 64
TX_C = "0x" + "c" * 64


def request(number, body="", created="2026-11-20T00:00:00Z"):
    return {"number": number, "title": "Fact request", "url": "https://example.test/1",
            "createdAt": created, "address": "0x" + "1" * 40, "chain": "base", "body": body}


def payment(tx, usdc=PRICE_USD, block=100):
    return {"tx": tx, "block": block, "from": "0x" + "2" * 40, "usdc": usdc}


class ReconcileTests(unittest.TestCase):
    def test_tx_hash_named_in_the_request_is_the_strongest_match(self):
        reqs, unmatched = reconcile([request(1, body="paid with " + TX_B)],
                                    [payment(TX_A), payment(TX_B)])
        self.assertTrue(reqs[0]["paid"])
        self.assertEqual(reqs[0]["tx"], TX_B)
        self.assertEqual(reqs[0]["matchMethod"], "tx_hash_in_request")
        self.assertEqual([p["tx"] for p in unmatched], [TX_A])

    def test_two_open_requests_and_one_payment_is_not_guessed(self):
        reqs, unmatched = reconcile([request(1), request(2)], [payment(TX_A)])
        self.assertFalse(any(r["paid"] for r in reqs))
        self.assertEqual(len(unmatched), 1)
        self.assertIn("no unambiguous match", reqs[0]["matchNote"])

    def test_single_request_and_single_payment_match(self):
        reqs, unmatched = reconcile([request(1)], [payment(TX_A)])
        self.assertTrue(reqs[0]["paid"])
        self.assertEqual(reqs[0]["matchMethod"], "only_open_request_and_payment")
        self.assertEqual(unmatched, [])

    def test_payment_older_than_the_request_does_not_pay_it(self):
        reqs, unmatched = reconcile([request(1, created="2026-11-20T00:00:00Z")],
                                    [payment(TX_A)],
                                    block_time=lambda block: "2026-11-19T23:00:00+00:00")
        self.assertFalse(reqs[0]["paid"])
        self.assertEqual(len(unmatched), 1)

    def test_payment_after_the_request_pays_it(self):
        reqs, _ = reconcile([request(1, created="2026-11-20T00:00:00Z")], [payment(TX_A)],
                            block_time=lambda block: "2026-11-20T00:05:00+00:00")
        self.assertTrue(reqs[0]["paid"])

    def test_dust_payment_is_not_revenue(self):
        reqs, unmatched = reconcile([request(1)], [payment(TX_A, usdc=0.000001)])
        self.assertFalse(reqs[0]["paid"])
        self.assertEqual(len(unmatched), 1)

    def test_one_payment_is_never_claimed_twice(self):
        reqs, _ = reconcile([request(1, body=TX_A), request(2, body=TX_A)], [payment(TX_A)])
        self.assertEqual(sum(1 for r in reqs if r["paid"]), 1)

    def test_revenue_only_counts_paid_requests(self):
        reqs, _ = reconcile([request(1), request(2)], [payment(TX_A, usdc=1.0)])
        self.assertEqual(sum(r.get("paidUsdc", 0) for r in reqs if r["paid"]), 0)


class InvoiceTests(unittest.TestCase):
    def tokens(self, count):
        return ["0x%040x" % (i * 7919) for i in range(count)]

    def test_amounts_are_unique_across_a_realistic_target_list(self):
        tokens = self.tokens(500)
        amounts = assign_amounts(tokens, 15.0, span=999)
        self.assertEqual(len(set(amounts.values())), len(tokens))

    def test_same_token_keeps_the_same_amount_between_runs(self):
        tokens = self.tokens(50)
        self.assertEqual(assign_amounts(tokens, 15.0), assign_amounts(list(reversed(tokens)), 15.0))

    def test_two_tokens_with_colliding_prefix_get_different_amounts(self):
        first = "0x" + "ab" * 20
        second = "0xab" + "cd" * 19
        amounts = assign_amounts([first, second], 0.5, span=9)
        self.assertNotEqual(amounts[first], amounts[second])

    def test_base_and_micro_tiers_never_share_an_amount(self):
        targets = [{"address": a, "reads": {"symbol": "T"}} for a in self.tokens(200)]
        mapping = invoice_map(targets)
        base = [i["amount_usdc"] for i in invoices(targets)]
        micro = [i["amount_usdc"] for i in micro_invoices(targets)]
        self.assertEqual(len(mapping), len(targets) * 2)
        self.assertFalse(set(base) & set(micro))

    def test_micro_amounts_stay_under_one_usdc(self):
        targets = [{"address": a, "reads": {"symbol": "T"}} for a in self.tokens(200)]
        self.assertTrue(all(i["amount_usdc"] < 1.0 for i in micro_invoices(targets)))


if __name__ == "__main__":
    unittest.main()

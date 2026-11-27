"""The durable paid rail: the payment must come from the chain, never from the issue text.

A stranger writes the issue, so the parser is a boundary. The only thing that may set
`paid` is a confirmed USDC transfer to AF; a hash that is pending, reverted, on another
chain, or that paid someone else must read as unpaid.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_paid_order as po  # noqa: E402

TX = "0x882a4c86508ebfa5f2e3cdfd40526373bcd728841eb20483a5bcb40423a5f890"
ADDR = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

BODY = f"""### Base USDC transaction hash

{TX}

### Token contract address (Base)

{ADDR}

### What do you need to know?

is the owner still able to mint?
"""

PAYMENT = {"status": "paid", "amount_usdc": 0.5, "payer": "0x2acfe5952ea0e78c73ea7ca5d709c3c1c13ab661",
           "block": 62872268, "confirmations": 30, "tx": TX}


class ParseTests(unittest.TestCase):
    def test_form_fields_are_extracted(self):
        f = po.parse_issue(BODY)
        self.assertEqual(f["tx"], TX)
        self.assertEqual(f["address"], ADDR)

    def test_a_body_without_a_hash_yields_none(self):
        self.assertIsNone(po.parse_issue("### Token contract address (Base)\n\n" + ADDR).get("tx"))

    def test_a_hash_embedded_in_prose_is_still_found(self):
        # parse_issue keeps the raw section; build_order is what applies the hash regex.
        f = po.parse_issue(f"### Base USDC transaction hash\n\npaid with tx {TX} thanks")
        self.assertEqual(po.TX.search(f["tx"]).group(0), TX)


class TierTests(unittest.TestCase):
    def test_the_floor_is_five_cents(self):
        self.assertIsNone(po.tier_for(0.049))
        self.assertEqual(po.tier_for(0.05), "check")

    def test_half_a_dollar_buys_the_pinned_report(self):
        self.assertEqual(po.tier_for(0.5), "report")
        self.assertEqual(po.tier_for(12.0), "report")


class OrderTests(unittest.TestCase):
    def _order(self, pay):
        o = {"schema": "af.paid_order.v1", "issue": 7, "at": "2026-11-27T00:00:00+00:00",
             "tx": TX, "address": ADDR, "question": "q", "pay_to": po.ss.AF, "paid": False,
             "amount_usdc": pay.get("amount_usdc", 0.0), "tier": None,
             "payer": pay.get("payer"), "self_test": False, "payment": pay}
        return o

    def test_no_hash_never_reaches_the_chain(self):
        o = po.build_order(1, "### Base USDC transaction hash\n\n(none)\n")
        self.assertEqual(o["status"], "unverified")
        self.assertFalse(o["paid"])

    def test_a_transfer_that_paid_someone_else_is_not_paid(self):
        # Real Base tx, real USDC transfer, recipient is not AF.
        v = po.verify(TX, pay_to="0x0000000000000000000000000000000000000001")
        self.assertEqual(v["status"], "no_transfer")
        self.assertNotIn("amount_usdc", v)

    def test_a_short_payment_is_underpaid_not_paid(self):
        o = self._order({**PAYMENT, "amount_usdc": 0.01})
        self.assertIsNone(po.tier_for(0.01))
        text = po.render_comment({**o, "status": "underpaid", "reason": "0.01 USDC is below the 0.05 USDC minimum"})
        self.assertIn("below the minimum", text)
        self.assertNotIn("Payment verified on chain", text)

    def test_an_unverified_reply_makes_no_payment_claim(self):
        o = self._order({"status": "not_found", "reason": "no receipt for this hash on Base"})
        text = po.render_comment({**o, "status": "unverified", "reason": o["payment"]["reason"]})
        self.assertIn("Not verified", text)
        self.assertIn("is a payment claim", text)

    def test_a_paid_reply_quotes_the_chain_evidence(self):
        o = self._order(PAYMENT)
        text = po.render_comment({**o, "status": "delivered_paid", "tier": "report",
                                  "report": {"reads": {"symbol": "USDC", "decimals": 6}},
                                  "verdict": "readable"})
        self.assertIn("Payment verified on chain", text)
        self.assertIn(PAYMENT["payer"], text)
        self.assertIn("30 confirmations", text)

    def test_the_reply_always_discloses_the_agent(self):
        o = self._order({"status": "no_transfer", "reason": "x"})
        self.assertIn("AI agent (OpenHands)", po.render_comment({**o, "status": "unverified",
                                                                 "reason": "x"}))


if __name__ == "__main__":
    unittest.main()

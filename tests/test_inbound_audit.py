"""The complete inbound audit must walk every chunk, and say so when it cannot.

`af_revenue_verify` only sees the last 49k blocks, so the 0.05 USDC payment at block
55,647,449 was invisible to the published ledger. This walks the whole range and records
any range the RPC refuses instead of reporting a silently short history.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_inbound_audit as audit  # noqa: E402
import af_revenue_verify as rv  # noqa: E402

AF = rv.AF_WALLET
SENDER = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"


def log(block, usdc, sender=SENDER):
    return {"transactionHash": "0x" + "ab" * 32, "blockNumber": hex(block),
            "topics": [rv.TRANSFER, "0x" + "0" * 24 + sender[2:], "0x" + "0" * 24 + AF[2:]],
            "data": hex(int(usdc * 10 ** 6)), "address": rv.USDC}


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.real = rv.rpc
        rv.time.sleep = lambda *_: None

    def tearDown(self):
        rv.rpc = self.real

    def fake(self, rows, refuse_wider_than=None):
        def rpc(method, params):
            rng = params[0]
            lo, hi = int(rng["fromBlock"], 16), int(rng["toBlock"], 16)
            self.calls.append((lo, hi))
            if refuse_wider_than is not None and hi - lo + 1 > refuse_wider_than:
                raise RuntimeError("rpc eth_getLogs failed: HTTP Error 403: Forbidden")
            return [r for r in rows if lo <= int(r["blockNumber"], 16) <= hi]
        return rpc

    def test_a_single_chunk_returns_its_rows(self):
        rv.rpc = self.fake([log(100, 0.05)])
        rows, unavailable = audit.scan(0, 10_000, chunk=20_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["usdc"], 0.05)
        self.assertEqual(unavailable, [])

    def test_the_range_is_covered_without_gaps(self):
        rv.rpc = self.fake([])
        audit.scan(0, 100, chunk=40)
        self.assertEqual([c[0] for c in self.calls], [0, 40, 80])
        self.assertEqual(self.calls[-1][1], 100)

    def test_a_refused_chunk_is_halved_until_it_fits(self):
        rv.rpc = self.fake([], refuse_wider_than=5_000)
        rows, unavailable = audit.scan(0, 10_000, chunk=20_000)
        self.assertEqual(rows, [])
        self.assertEqual(unavailable, [])
        # the wide attempts are refused, then the same range is retried narrower
        self.assertTrue(any(hi - lo + 1 <= 5_000 for lo, hi in self.calls))

    def test_a_range_the_rpc_never_serves_is_reported_not_hidden(self):
        rv.rpc = self.fake([], refuse_wider_than=0)
        rows, unavailable = audit.scan(0, 4_000, chunk=25_000)
        self.assertEqual(rows, [])
        self.assertTrue(unavailable, "a refused range must be recorded")
        self.assertEqual(unavailable[0][0], 0)


class ClassificationTests(unittest.TestCase):
    def test_a_cow_settlement_payment_is_not_customer_revenue(self):
        self.assertEqual(rv.classify_transfer(SENDER, set()), "swap")

    def test_the_audit_output_names_every_bucket(self):
        source = Path("tools/af_inbound_audit.py").read_text(encoding="utf-8")
        for key in ('k + "_total"', '"unavailable_ranges"', '"revenue_basis"',
                    "own_trade", "summarise"):
            self.assertIn(key, source)


if __name__ == "__main__":
    unittest.main()

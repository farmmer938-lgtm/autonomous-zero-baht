import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import af_selfserve as ss
import goal72h_close as g

AF = ss.AF.lower()
K = g.K_WALLET
STRANGER = "0x" + "9" * 40
DEADLINE = datetime.fromisoformat(g.GOAL_DEADLINE.replace("Z", "+00:00"))


def transfer(usdc_units=50_000, frm=STRANGER, block=62_900_000):
    return {"tx": "0x" + "a" * 64, "block": block, "units": usdc_units,
            "usdc": usdc_units / 1e6, "from": frm}


class VerdictTests(unittest.TestCase):
    def test_a_strangers_payment_passes_before_the_deadline(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[transfer()])
        self.assertEqual(v["status"], "PASS")
        self.assertEqual(v["payer"], STRANGER)
        self.assertEqual(v["amount_usdc"], 0.05)

    def test_exactly_five_cents_is_enough(self):
        self.assertEqual(g.verdict(now=DEADLINE.replace(day=28), transfers=[transfer(50_000)])["status"], "PASS")

    def test_below_five_cents_does_not_pass(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[transfer(49_999)])
        self.assertEqual(v["status"], "OPEN")
        self.assertIn("below", v["excluded"][0]["why"])

    def test_a_self_send_never_passes(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[transfer(frm=AF)])
        self.assertEqual(v["status"], "OPEN")
        self.assertEqual(v["excluded"][0]["why"], "payer is AF or K")

    def test_ks_wallet_is_not_a_customer(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[transfer(frm=K)])
        self.assertEqual(v["status"], "OPEN")

    def test_open_until_the_deadline_then_fail(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[])
        self.assertEqual(v["status"], "OPEN")
        self.assertGreater(v["hours_left"], 0)
        v = g.verdict(now=DEADLINE, transfers=[])
        self.assertEqual(v["status"], "FAIL")
        self.assertEqual(v["payer_count"], 0)

    def test_the_first_qualifying_payment_is_the_one_reported(self):
        v = g.verdict(now=DEADLINE.replace(day=28),
                      transfers=[transfer(block=62_900_002), transfer(block=62_900_001)])
        self.assertEqual(v["block"], 62_900_001)

    def test_the_verdict_names_its_scan_window(self):
        v = g.verdict(now=DEADLINE.replace(day=28), transfers=[], start_block=62_860_000)
        self.assertEqual(v["scan"], {"from_block": 62_860_000, "to_block": 62_860_000})


class ScanTests(unittest.TestCase):
    def test_scan_reads_only_transfers_into_af(self):
        calls = []

        def fake_rpc(method, params):
            calls.append(params[0])
            return [{"blockNumber": hex(62_900_005), "transactionHash": "0x" + "b" * 64,
                     "data": hex(75_000), "topics": [ss.TRANSFER, "0x" + "0" * 24 + STRANGER[2:],
                                                     "0x" + "0" * 24 + AF[2:]]}]

        original = ss.rpc
        ss.rpc = fake_rpc
        try:
            out = g.scan(62_900_000, end_block=62_900_010)
        finally:
            ss.rpc = original
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["from"], STRANGER)
        self.assertEqual(out[0]["usdc"], 0.075)
        topic = calls[0]["topics"][2]
        self.assertTrue(topic.endswith(AF[2:]), "the log filter must ask for AF as the recipient")

    def test_scan_chunks_a_long_range(self):
        ranges = []

        def fake_rpc(method, params):
            q = params[0]
            ranges.append((int(q["fromBlock"], 16), int(q["toBlock"], 16)))
            return []

        original = ss.rpc
        ss.rpc = fake_rpc
        try:
            g.scan(1000, end_block=1000 + 3 * g.CHUNK)
        finally:
            ss.rpc = original
        self.assertEqual(len(ranges), 4)
        self.assertEqual(ranges[0][0], 1000)
        self.assertEqual(ranges[-1][1], 1000 + 3 * g.CHUNK)


if __name__ == "__main__":
    unittest.main()

"""E2 pages must differ in facts, must carry a block and a hash, and must never claim safety."""
import html
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_e2_panel as e2  # noqa: E402

LEDGER = Path("data/e2_panel.json")
PAGES = sorted(Path("site/audit/e2").glob("*.html"))
# Mentions of "honeypot" are allowed only in a negation; these are the claim forms.
FORBIDDEN = ("is safe", "safe to buy", "certified", "guaranteed", "will pump",
             "audited by", "honeypot detection", "detects honeypots", "honeypot-free")


class SelectionTests(unittest.TestCase):
    def test_selection_is_by_volume_deduped_by_address(self):
        rows = [{"address": "0xa", "h24_volume_usd": 5}, {"address": "0xb", "h24_volume_usd": 9},
                {"address": "0xa", "h24_volume_usd": 99}]
        out = e2.select(rows, limit=2)
        self.assertEqual([r["address"] for r in out], ["0xa", "0xb"])

    def test_limit_is_respected(self):
        rows = [{"address": "0x%d" % i, "h24_volume_usd": i} for i in range(30)]
        self.assertEqual(len(e2.select(rows, limit=10)), 10)

    def test_candidates_keep_the_deepest_pool_per_token(self):
        payload = {"data": [
            {"attributes": {"name": "AAA / WETH", "volume_usd": {"h24": "10"}, "reserve_in_usd": "1"},
             "relationships": {"base_token": {"data": {"id": "base_0xAbC"}}}},
            {"attributes": {"name": "AAA / USDC", "volume_usd": {"h24": "90"}, "reserve_in_usd": "2"},
             "relationships": {"base_token": {"data": {"id": "base_0xabc"}}}},
        ]}
        rows = e2.candidates(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["h24_volume_usd"], 90)


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.cases = cls.ledger["cases"]

    def test_panel_is_ten_tokens_or_fewer_with_unique_addresses(self):
        self.assertLessEqual(len(self.cases), 10)
        addrs = [c["address"] for c in self.cases]
        self.assertEqual(len(addrs), len(set(addrs)))

    def test_every_case_carries_block_hash_and_unchecked_list(self):
        for c in self.cases:
            self.assertIsInstance(c["block"], int, c["slug"])
            self.assertRegex(c["report_sha256"], r"^[0-9a-f]{64}$")
            self.assertIsInstance(c["not_established"], list)
            self.assertTrue(c["selection_evidence"]["source_url"].startswith("https://"))

    def test_pages_do_not_pretend_to_detect_honeypots_or_certify(self):
        for p in [x for x in PAGES if x.name != "index.html"]:
            text = p.read_text(encoding="utf-8").lower()
            for bad in FORBIDDEN:
                self.assertNotIn(bad, text, f"{p.name}: {bad}")
            self.assertIn("cannot tell you", text)
            self.assertIn("no swap was simulated", text)

    def test_pages_are_not_copies_of_each_other(self):
        """Two pages must differ in the facts they state, not only in their title."""
        facts = set()
        for c in self.cases:
            key = (c["address"], c["block"], tuple(c.get("flags") or []), c["report_sha256"])
            facts.add(key)
        self.assertEqual(len(facts), len(self.cases))

    def test_a_duplicate_symbol_is_kept_apart_by_address(self):
        """AERO appeared twice with different contracts; the panel must not merge them."""
        aero = [c for c in self.cases if c["symbol"] == "AERO"]
        if len(aero) > 1:
            self.assertEqual(len({c["address"] for c in aero}), len(aero))

    def test_index_links_every_page(self):
        index = Path("site/audit/e2/index.html").read_text(encoding="utf-8")
        for c in self.cases:
            self.assertIn(c["slug"] + ".html", index)


class IndexTests(unittest.TestCase):
    def test_index_states_the_limit_and_the_source(self):
        text = Path("site/audit/e2/index.html").read_text(encoding="utf-8").lower()
        self.assertIn("proxy for attention, not for demand", text)
        self.assertIn("none of these pages is a safety certification", text)
        self.assertIn("application/ld+json", text)


if __name__ == "__main__":
    unittest.main()

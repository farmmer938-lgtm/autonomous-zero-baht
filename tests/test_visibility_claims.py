"""The stages a share cannot buy: discovered, reach and traffic stay null until a system counts."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_funnel as fn  # noqa: E402


def run(**over):
    kw = {"issue_rows": [], "order_rows": [], "paid": {}, "published": {"published": 9}}
    kw.update(over)
    return fn.compute(kw["issue_rows"], kw["order_rows"], kw["paid"], kw["published"])


class EvidenceGateTests(unittest.TestCase):
    def test_discovery_and_visit_are_null_even_with_pages_published(self):
        f = run(published={"published": 9})
        self.assertEqual(f["published"], 9)
        self.assertIsNone(f["discovered"])
        self.assertIsNone(f["reach"])
        self.assertIsNone(f["traffic"])

    def test_a_share_is_not_an_input_to_any_stage(self):
        """There is no share/referral input that can raise reach: the only referral field
        records where a real order came from."""
        f = run(order_rows=[{"issue": 2, "status": "delivered_unpaid", "referral": "x"}])
        self.assertIsNone(f["reach"])
        self.assertIsNone(f["discovered"])
        self.assertEqual(f["referrals"], ["x"])

    def test_each_gated_stage_carries_its_evidence_requirement(self):
        for key in ("discovered_note", "reach_note", "traffic_note"):
            self.assertTrue(run()[key], key)

    def test_stage_order_keeps_published_first_and_money_last(self):
        stages = list(fn.STAGES)
        self.assertEqual(stages[0], "published")
        self.assertEqual(stages[-1], "net_revenue")
        self.assertLess(stages.index("discovered"), stages.index("reach"))


class ShareKitTests(unittest.TestCase):
    def test_the_share_copy_blocks_never_overclaim(self):
        """Only the quoted copy counts: the doc may mention a word in order to forbid it."""
        doc = Path("docs/PHASE_M_VISIBILITY.md").read_text(encoding="utf-8")
        quotes = [l.lower() for l in doc.splitlines() if l.startswith("> ")]
        self.assertGreaterEqual(len(quotes), 2)
        for line in quotes:
            for forbidden in ("certified", "honeypot-tested", "audited by", "guaranteed",
                              "verified safe"):
                self.assertNotIn(forbidden, line, line[:60])

    def test_the_audit_page_renders_a_link_preview(self):
        html = Path("site/audit/index.html").read_text(encoding="utf-8")
        for tag in ('property="og:title"', 'property="og:description"',
                    'property="og:url"', 'name="twitter:card"'):
            self.assertIn(tag, html, tag)


if __name__ == "__main__":
    unittest.main()

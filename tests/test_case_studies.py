"""J1/J2: the evidence pages must not drift from the data or invent an index.

A case study is only worth reading if the block, the hash and the "not established" list on
the page are the same ones in the JSON beside it. And no guide may claim the site is indexed
— HTTP 200 is not an audience.
"""
import json
import re
import unittest
from pathlib import Path

CASES = Path("site/audit/cases")
GUIDES = Path("site/audit/guides")
SITE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht/"


class CaseStudyTests(unittest.TestCase):
    def setUp(self):
        self.files = sorted(p for p in CASES.glob("*.json"))

    def test_three_cases_exist(self):
        self.assertGreaterEqual(len(self.files), 3)

    def test_each_case_quotes_a_block_and_a_hash(self):
        for p in self.files:
            c = json.loads(p.read_text(encoding="utf-8"))
            self.assertIsInstance(c["block"], int, p.name)
            self.assertRegex(c["report_sha256"], r"^[0-9a-f]{64}$", p.name)

    def test_each_case_lists_what_it_did_not_establish(self):
        for p in self.files:
            c = json.loads(p.read_text(encoding="utf-8"))
            self.assertTrue(c["not_established"], p.name)

    def test_the_verdicts_are_not_all_the_same(self):
        verdicts = {json.loads(p.read_text(encoding="utf-8"))["verdict"] for p in self.files}
        self.assertGreaterEqual(len(verdicts), 3, "a shop showing one verdict is a brochure")

    def test_the_page_carries_the_block_of_every_case(self):
        html = (CASES / "index.html").read_text(encoding="utf-8")
        for p in self.files:
            c = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn(str(c["block"]), html, f"{p.name} block missing from the page")
            self.assertIn(c["report_sha256"][:24], html, f"{p.name} hash missing")

    def test_the_page_never_claims_certification(self):
        html = (CASES / "index.html").read_text(encoding="utf-8").lower()
        self.assertIn("not a safety certification", html)

    def test_the_free_scanner_column_is_quoted_not_summarised(self):
        for p in self.files:
            c = json.loads(p.read_text(encoding="utf-8"))
            if c.get("free_scanner"):
                for k in c["free_scanner"]:
                    self.assertTrue(k.islower() or "_" in k, k)


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.pages = sorted(GUIDES.glob("*.html"))

    def test_at_least_three_guides(self):
        self.assertGreaterEqual(len(self.pages), 3)

    def test_each_guide_has_canonical_description_and_article_schema(self):
        for p in self.pages:
            h = p.read_text(encoding="utf-8")
            self.assertIn('rel="canonical"', h, p.name)
            self.assertIn('<meta name="description"', h, p.name)
            self.assertIn('"@type":"Article"', h, p.name)
            self.assertIn(f"{SITE}audit/guides/{p.name}", h, p.name)

    def test_each_guide_links_back_to_the_offer_and_to_another_guide(self):
        for p in self.pages:
            h = p.read_text(encoding="utf-8")
            self.assertIn('href="../"', h, p.name)
            others = [q.name for q in self.pages if q.name != p.name]
            self.assertTrue(any(o in h for o in others), f"{p.name} is an orphan")

    def test_each_guide_carries_the_order_form(self):
        for p in self.pages:
            self.assertIn("issues/new?template=audit-request.json",
                          p.read_text(encoding="utf-8"), p.name)

    def test_no_guide_claims_indexing_traffic_or_customers(self):
        forbidden = ("indexed by google", "ranked", "customers have", "our users",
                     "trusted by")
        for p in self.pages:
            low = p.read_text(encoding="utf-8").lower()
            for f in forbidden:
                self.assertNotIn(f, low, f"{p.name} claims {f!r}")

    def test_every_guide_is_in_the_sitemap(self):
        sm = Path("site/sitemap.xml").read_text(encoding="utf-8")
        for p in self.pages:
            self.assertIn(f"audit/guides/{p.name}", sm, p.name)
        self.assertIn("audit/cases/", sm)


if __name__ == "__main__":
    unittest.main()

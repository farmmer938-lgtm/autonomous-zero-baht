"""I1/I2/I3: the sales page, the order form and the payment code must say the same thing.

A landing page that quotes a price the cashier does not charge, or a pay-to address that is
not the wallet the verifier watches, is worse than no page: it takes money into a hole. These
tests are the only thing keeping the three files agreeing.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_selfserve as ss  # noqa: E402
import af_revenue_verify as rv  # noqa: E402

PAGE = Path("site/audit/index.html")
FORM = Path(".github/ISSUE_TEMPLATE/audit-request.json")


def page():
    return PAGE.read_text(encoding="utf-8")


class PriceAgreementTests(unittest.TestCase):
    def test_the_page_quotes_the_micro_tier_the_cashier_charges(self):
        price = ss.MICRO_TIER["usdc"]
        self.assertIn(f"{price:.2f} USDC", page())
        self.assertIn(f'"price":"{price:.2f}"', page().replace(" ", ""))

    def test_the_pay_to_address_is_the_watched_wallet(self):
        self.assertIn(ss.AF, page())
        self.assertEqual(ss.AF.lower(), rv.AF_WALLET.lower())

    def test_the_page_does_not_quote_a_price_the_cashier_cannot_match(self):
        for other in ("1.00 USDC", "5 USDC", "15 USDC"):
            self.assertNotIn(other, page())


class SampleTests(unittest.TestCase):
    def test_every_sample_link_exists(self):
        refs = re.findall(r'href="\.\./reviews/([^"]+\.json)"', page())
        self.assertGreaterEqual(len(refs), 3, "a sales page needs at least three samples")
        for ref in refs:
            self.assertTrue((Path("site/reviews") / ref).exists(), ref)

    def test_every_sample_is_a_real_report_with_a_verdict(self):
        for ref in re.findall(r'href="\.\./reviews/([^"]+\.json)"', page()):
            rep = json.loads((Path("site/reviews") / ref).read_text(encoding="utf-8"))
            self.assertIn("verdict", rep, ref)
            self.assertIn("address", rep, ref)


class OrderFormTests(unittest.TestCase):
    def setUp(self):
        self.form = json.loads(FORM.read_text(encoding="utf-8"))

    def test_the_form_exists_where_the_page_links(self):
        self.assertIn("issues/new?template=audit-request.json", page())

    def test_the_form_carries_the_label_the_responder_watches(self):
        self.assertIn("audit-request", self.form["labels"])

    def test_the_form_asks_for_the_two_fields_the_engine_needs(self):
        ids = {b["id"] for b in self.form["body"]}
        self.assertIn("chain", ids)
        self.assertIn("address", ids)

    def test_the_address_field_is_required(self):
        body = {b["id"]: b for b in self.form["body"]}
        self.assertTrue(body["address"]["validations"]["required"])


class DiscoverabilityTests(unittest.TestCase):
    def test_the_sitemap_lists_the_sales_page(self):
        self.assertIn("/audit/", Path("site/sitemap.xml").read_text(encoding="utf-8"))

    def test_robots_points_at_the_sitemap(self):
        self.assertIn("sitemap.xml", Path("site/robots.txt").read_text(encoding="utf-8"))

    def test_the_page_declares_canonical_and_service_schema(self):
        html = page()
        self.assertIn('rel="canonical"', html)
        self.assertIn('"@type":"Service"', html)

    def test_the_page_states_what_is_not_included(self):
        self.assertIn("Not included", page())
        self.assertIn("investment advice", page().lower())


if __name__ == "__main__":
    unittest.main()

"""Phase N: one price, no phantom council, and no stage invented from a decision."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(".")
PAGES = ["site/audit/index.html", "site/index.html", "site/store.html",
         ".github/ISSUE_TEMPLATE/audit-request.json", "docs/SERVICE_AUDIT.md"]
PRICE = "0.50"


class PriceTests(unittest.TestCase):
    def test_no_page_advertises_750_baht(self):
        for p in PAGES:
            text = Path(p).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\b750\s*(บาท|baht|thb)\b", text, re.I), p)

    def test_the_offer_pages_agree_on_one_price(self):
        audit = Path("site/audit/index.html").read_text(encoding="utf-8")
        self.assertIn(PRICE, audit)
        tool = Path("tools/af_selfserve.py").read_text(encoding="utf-8")
        self.assertIn('"usdc": 0.5', tool)

    def test_the_pay_to_address_is_the_one_the_tool_prints(self):
        """The page and the order tool must name the same wallet: the tool takes it from
        af_selfserve.AF, so that module is the source of truth."""
        addr = "0xf3C99a6d6e7C6b2ae00b44dC42cC3eb7691D7702"
        self.assertIn(addr, Path("site/audit/index.html").read_text(encoding="utf-8"))
        self.assertIn(addr, Path("tools/af_selfserve.py").read_text(encoding="utf-8"))
        self.assertIn("PAY_TO = ss.AF", Path("tools/af_audit_order.py").read_text(
            encoding="utf-8"))


class CouncilHonestyTests(unittest.TestCase):
    def test_no_council_artifacts_are_claimed_to_exist(self):
        """If a council is ever built, its files must exist before any doc claims it ran."""
        doc = Path("docs/PHASE_N_COUNCIL.md").read_text(encoding="utf-8")
        claims_council = "the council reviewed" in doc.lower().replace(
            "council reviewed", "the council reviewed") and "not a council" not in doc.lower()
        self.assertFalse(claims_council)
        self.assertIn("does not exist", doc.lower())

    def test_kpi_nulls_are_not_numbers_in_the_doc(self):
        doc = Path("docs/PHASE_N_COUNCIL.md").read_text(encoding="utf-8")
        for line in doc.splitlines():
            if line.startswith("| 1 ") or line.startswith("| 2 "):
                self.assertIn("null" if line.startswith("| 1 ") else "0", line)

    def test_review_record_states_zero_evidence(self):
        rec = json.loads(Path("data/phase_n_review.json").read_text(encoding="utf-8"))
        self.assertIsNone(rec["kpi"]["humans_reached"])
        self.assertEqual(rec["kpi"]["real_enquiries"], 0)
        self.assertEqual(rec["kpi"]["cash_received_usdc"], 0)
        self.assertEqual(rec["risk_register"][0]["severity"] in ("high", "medium", "low"), True)


if __name__ == "__main__":
    unittest.main()


class DeployHonestyTests(unittest.TestCase):
    """A build that succeeded must still publish: housekeeping steps may not abort a deploy."""

    def test_artifact_cleanup_cannot_fail_the_deploy(self):
        wf = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
        self.assertIn("Delete older deploy artifacts", wf)
        block = wf.split("Delete older deploy artifacts", 1)[1].split("- name:", 1)[0]
        self.assertIn("|| true", block, "cleanup must tolerate an API error")
        self.assertIn("2>/dev/null", block)

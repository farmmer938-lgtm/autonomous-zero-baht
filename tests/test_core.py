import json
import unittest
from engine.content import create_draft

class CoreTests(unittest.TestCase):
    def test_draft_does_not_claim_personal_experience(self):
        draft = create_draft({"title": "Example guide", "url": "https://example.com", "summary": "Example summary", "source": "feed", "score": 1})
        self.assertFalse(draft["first_hand_experience_claimed"])
        self.assertEqual(draft["status"], "draft_requires_human_review")
        self.assertIn("affiliate_disclosure", draft["formats"])

    def test_no_payment_guard_config(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config" / "system.json").read_text(encoding="utf-8"))
        self.assertEqual(config["budget_thb"], 0)
        self.assertTrue(config["no_payment_guard"])

if __name__ == "__main__":
    unittest.main()

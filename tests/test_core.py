import json
import unittest
from engine.content import create_draft
from engine.research import _dedupe, _score_item


class CoreTests(unittest.TestCase):
    def test_draft_does_not_claim_personal_experience(self):
        draft = create_draft({"title": "Example guide", "url": "https://example.com", "summary": "Example summary", "source": "feed", "score": 1})
        self.assertFalse(draft["first_hand_experience_claimed"])
        self.assertEqual(draft["status"], "draft_requires_human_review")
        self.assertIn("affiliate_disclosure", draft["formats"])
        self.assertEqual(draft["research_score"], 0)
        self.assertEqual(draft["research_quality"], "unknown")

    def test_no_payment_guard_config(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "config" / "system.json").read_text(encoding="utf-8"))
        self.assertEqual(config["budget_thb"], 0)
        self.assertTrue(config["no_payment_guard"])

    def test_research_scoring_rewards_intent(self):
        matched, keyword_score, intent_score, total = _score_item(
            {"title": "How to compare tools", "summary": "A guide to price and features"},
            ["how to", "compare", "guide", "price"],
        )
        self.assertIn("how to", matched)
        self.assertGreaterEqual(intent_score, 2)
        self.assertEqual(total, keyword_score + intent_score)

    def test_seed_research_is_not_publishable(self):
        draft = create_draft({
            "title": "Seed topic", "url": "https://example.com",
            "summary": "unverified", "source": "local_seed_data",
            "research_quality": "seed_unverified", "opportunity_score": 2,
        })
        self.assertEqual(draft["research_quality"], "seed_unverified")

    def test_research_deduplication(self):
        items = [
            {"title": " Same topic ", "url": "https://example.com/a"},
            {"title": "same topic", "url": "https://example.com/a"},
            {"title": "Other topic", "url": "https://example.com/b"},
        ]
        self.assertEqual(len(_dedupe(items)), 2)


    def test_stale_item_is_marked_unverified(self):
        from engine.research import _freshness
        self.assertEqual(_freshness({"published": "2022-01-01T00:00:00+00:00"}, max_age_days=30), "stale_unverified")

    def test_missing_published_date_is_unverified(self):
        from engine.research import _freshness
        self.assertEqual(_freshness({"published": ""}, max_age_days=30), "date_unverified")

if __name__ == "__main__":
    unittest.main()

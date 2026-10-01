import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engine.content import create_draft, generate_drafts
from engine.research import _dedupe, _freshness, _score_item


class CoreTests(unittest.TestCase):
    def test_draft_does_not_claim_personal_experience(self):
        draft = create_draft({"title": "Example guide", "url": "https://example.com", "summary": "Example summary", "source": "feed", "score": 1})
        self.assertFalse(draft["first_hand_experience_claimed"])
        self.assertEqual(draft["status"], "draft_requires_human_review")
        self.assertIn("affiliate_disclosure", draft["formats"])
        self.assertEqual(draft["research_score"], 0)
        self.assertEqual(draft["research_quality"], "unknown")

    def test_no_payment_guard_config(self):
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
        self.assertEqual(
            _freshness({"published": "2022-01-01T00:00:00+00:00"}, max_age_days=30),
            "stale_unverified",
        )

    def test_missing_published_date_is_unverified(self):
        self.assertEqual(
            _freshness({"published": ""}, max_age_days=30),
            "date_unverified",
        )

    def test_draft_generation_skips_unverified_items(self):
        items = [
            {"title": "stale", "freshness": "stale_unverified", "research_quality": "stale_unverified"},
            {"title": "missing-date", "freshness": "date_unverified", "research_quality": "stale_unverified"},
            {"title": "fresh", "freshness": "fresh", "research_quality": "public_feed", "url": "https://example.com", "source": "feed"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_drafts(items, limit=5, output_dir=tmp)
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].endswith("fresh.json"))
            self.assertTrue(Path(tmp, "fresh.json").exists())

    def test_rfc822_published_date_is_parsed(self):
        item = {"published": "Thu, 01 Oct 2026 01:00:00 GMT"}
        now = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(_freshness(item, max_age_days=30, now=now), "fresh")


if __name__ == "__main__":
    unittest.main()

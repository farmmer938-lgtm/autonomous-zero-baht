import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from engine.content import create_draft, generate_drafts
from engine.research import _dedupe, _freshness, _score_item
from engine.validator import validate_drafts


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


    def test_validator_rejects_stale_and_unsafe_urls(self):
        draft = create_draft({"title": "Unsafe", "url": "javascript:alert(1)", "summary": "x", "source": "feed", "research_quality": "public_feed", "freshness": "stale_unverified"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            import engine.validator as validator
            original = validator.ROOT
            try:
                validator.ROOT = Path(tmp)
                result = validate_drafts(["draft.json"])
            finally:
                validator.ROOT = original
            self.assertFalse(result[0]["passed"])
            self.assertIn("invalid_source_url", result[0]["errors"])
            self.assertIn("unverified_freshness", result[0]["errors"])


    def test_validator_accepts_https_source_url(self):
        draft = create_draft({"title": "Safe", "url": "https://example.com", "summary": "x", "source": "feed", "research_quality": "public_feed", "freshness": "fresh"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
            import engine.validator as validator
            original = validator.ROOT
            try:
                validator.ROOT = Path(tmp)
                result = validate_drafts(["draft.json"])
            finally:
                validator.ROOT = original
            self.assertTrue(result[0]["passed"])

    def test_feed_retry_is_bounded_and_recovers(self):
        import engine.research as research
        calls = {"count": 0}
        original = research._fetch_feed

        def flaky_fetch(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise TimeoutError("temporary")
            return [{
                "title": "Fresh guide",
                "url": "https://example.com/guide",
                "summary": "how to guide",
                "source": args[0],
                "published": "2026-10-01T00:00:00+00:00",
            }]

        research._fetch_feed = flaky_fetch
        try:
            items = research.run_research({
                "rss_feeds": ["https://feed.example.test/rss"],
                "user_agent": "test",
                "max_items_per_feed": 20,
                "max_feed_retries": 2,
                "max_age_days": 30,
                "keywords": ["guide"],
                "max_drafts_per_run": 5,
            })
        finally:
            research._fetch_feed = original
        self.assertEqual(calls["count"], 2)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["research_quality"], "public_feed")

    def test_feed_retry_stops_after_configured_bound(self):
        import engine.research as research
        calls = {"count": 0}
        original = research._fetch_feed

        def always_fail(*args, **kwargs):
            calls["count"] += 1
            raise TimeoutError("persistent")

        research._fetch_feed = always_fail
        try:
            items = research.run_research({
                "rss_feeds": ["https://feed.example.test/rss"],
                "user_agent": "test",
                "max_items_per_feed": 20,
                "max_feed_retries": 2,
                "max_age_days": 30,
                "keywords": ["guide"],
                "max_drafts_per_run": 5,
            })
        finally:
            research._fetch_feed = original
        self.assertEqual(calls["count"], 3)
        self.assertEqual(len(items), 2)
        self.assertTrue(all(item["research_quality"] == "seed_unverified" for item in items))

    def test_rfc822_published_date_is_parsed(self):
        item = {"published": "Thu, 01 Oct 2026 01:00:00 GMT"}
        now = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(_freshness(item, max_age_days=30, now=now), "fresh")

    def test_main_fails_on_unexpected_research_engine_error(self):
        import engine.run as run
        from unittest.mock import patch

        with patch.object(run, "run_research", side_effect=RuntimeError("unexpected research failure")):
            with self.assertRaises(RuntimeError):
                run.main()

    def test_draft_generation_prevents_slug_collisions(self):
        items = [
            {"title": "A/B", "freshness": "fresh", "research_quality": "public_feed", "url": "https://example.com/a", "source": "feed"},
            {"title": "A B", "freshness": "fresh", "research_quality": "public_feed", "url": "https://example.com/b", "source": "feed"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_drafts(items, limit=5, output_dir=tmp)
            self.assertEqual(len(paths), 2)
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(Path(paths[0]).exists())
            self.assertTrue(Path(paths[1]).exists())

    def test_draft_generation_rejects_non_positive_limit(self):
        items = [{
            "title": "fresh",
            "freshness": "fresh",
            "research_quality": "public_feed",
            "url": "https://example.com",
            "source": "feed",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(generate_drafts(items, limit=0, output_dir=tmp), [])
            self.assertEqual(generate_drafts(items, limit=-1, output_dir=tmp), [])


if __name__ == "__main__":
    unittest.main()

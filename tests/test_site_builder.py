import json
import tempfile
import unittest
from pathlib import Path

import engine.site_builder as site_builder


def _draft():
    return {
        "id": "example-topic",
        "source_title": "Example Topic",
        "source_url": "https://example.com/a",
        "research_score": 5,
        "status": "draft_requires_human_review",
        "formats": {
            "seo_article_outline": {
                "title": "Example Topic",
                "sections": ["ข้อหนึ่ง", "ข้อสอง"],
                "source_summary_for_editor": "สรุปสั้น",
            },
            "affiliate_disclosure": "Disclosure: may earn commission",
        },
    }


class SiteBuilderTests(unittest.TestCase):
    def test_builds_index_and_post_from_validated_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / "data" / "content" / "drafts"
            drafts.mkdir(parents=True)
            (drafts / "example-topic.json").write_text(
                json.dumps(_draft(), ensure_ascii=False), encoding="utf-8")

            orig_root, orig_site, orig_posts = site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR
            try:
                site_builder.ROOT = root
                site_builder.SITE_DIR = root / "site"
                site_builder.POSTS_DIR = root / "site" / "p"
                record = site_builder.build_site(["data/content/drafts/example-topic.json"])
            finally:
                site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR = orig_root, orig_site, orig_posts

            self.assertEqual(record["pages_built"], 1)
            index = (root / "site" / "index.html").read_text(encoding="utf-8")
            post = (root / "site" / "p" / "example-topic.html").read_text(encoding="utf-8")
            manifest = json.loads((root / "site" / "index.json").read_text(encoding="utf-8"))
            self.assertIn("Example Topic", index)
            self.assertIn("Example Topic", post)
            self.assertIn("https://example.com/a", post)
            self.assertEqual(manifest["count"], 1)

    def test_skips_non_publishable_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            drafts = root / "data" / "content" / "drafts"
            drafts.mkdir(parents=True)
            bad = _draft()
            bad["status"] = "seed_unverified"
            (drafts / "bad.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")

            orig_root, orig_site, orig_posts = site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR
            try:
                site_builder.ROOT = root
                site_builder.SITE_DIR = root / "site"
                site_builder.POSTS_DIR = root / "site" / "p"
                record = site_builder.build_site(["data/content/drafts/bad.json"])
            finally:
                site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR = orig_root, orig_site, orig_posts

            self.assertEqual(record["pages_built"], 0)

    def test_missing_draft_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            orig_root, orig_site, orig_posts = site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR
            try:
                site_builder.ROOT = root
                site_builder.SITE_DIR = root / "site"
                site_builder.POSTS_DIR = root / "site" / "p"
                record = site_builder.build_site(["data/content/drafts/nope.json"])
            finally:
                site_builder.ROOT, site_builder.SITE_DIR, site_builder.POSTS_DIR = orig_root, orig_site, orig_posts
            self.assertEqual(record["pages_built"], 0)


if __name__ == "__main__":
    unittest.main()

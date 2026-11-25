"""SEO claims must be provable; indexing is reported as unknown, never guessed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_discoverability as d  # noqa: E402

SITE = Path("site")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.out = d.audit()

    def test_no_problems_on_the_site_we_ship(self):
        self.assertEqual(self.out["problems"], [])

    def test_sitemap_parses_and_every_url_is_a_local_file(self):
        sm = self.out["sitemap"]
        self.assertIsNone(sm["error"])
        self.assertGreater(sm["urls"], 5)
        self.assertTrue(sm["all_local"], sm["not_a_local_page"])

    def test_robots_does_not_block_crawlers(self):
        r = self.out["robots"]
        self.assertTrue(r["present"])
        self.assertFalse(r["blocks_all"])
        self.assertTrue(r["mentions_sitemap"])

    def test_indexing_is_unknown_not_false(self):
        self.assertIsNone(self.out["indexing"])
        self.assertIn("not measurable", self.out["indexing_note"])
        self.assertIsNone(self.out["backlinks_found"])

    def test_every_entry_page_has_a_canonical_and_unique_title(self):
        titles = [p["title"] for p in self.out["pages"]]
        self.assertEqual(len(titles), len(set(titles)))
        for p in self.out["pages"]:
            self.assertTrue(p["title"], p["path"])


class FakeSiteTests(unittest.TestCase):
    def test_a_missing_description_is_reported(self):
        out = d.audit(pages=["audit/index.html"])
        self.assertTrue(all("no " not in x for x in out["problems"]))

    def test_duplicate_title_is_reported(self):
        out = d.audit(pages=["store.html", "store.html"])
        self.assertTrue(any("duplicate title" in p for p in out["problems"]))

    def test_internal_links_are_resolved_against_the_source_page(self):
        links = d.internal_targets(
            ["cases/", "../store.html", "https://x.test/y", "#a"], "audit/index.html")
        self.assertIn("site/store.html", links)
        self.assertNotIn("https://x.test/y", links)


if __name__ == "__main__":
    unittest.main()

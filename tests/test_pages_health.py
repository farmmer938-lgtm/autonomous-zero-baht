"""The Pages health report must notice the failures that have already happened once."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_pages_health as health  # noqa: E402


class ArtifactVerdictTests(unittest.TestCase):
    def test_normal_usage_is_ok(self):
        level, detail = health.artifact_verdict(61 * 1024 * 1024)
        self.assertEqual(level, "ok")
        self.assertIn("61 MB", detail)

    def test_usage_near_the_quota_warns(self):
        self.assertEqual(health.artifact_verdict(250 * 1024 * 1024)[0], "warn")

    def test_usage_that_would_swallow_the_next_deploy_fails(self):
        level, detail = health.artifact_verdict(460 * 1024 * 1024)
        self.assertEqual(level, "fail")
        self.assertIn("may not be kept", detail)


class DeployVerdictTests(unittest.TestCase):
    def test_site_matching_main_is_ok(self):
        self.assertEqual(health.deploy_verdict("a" * 40, "a" * 40)[0], "ok")

    def test_a_lagging_site_fails(self):
        level, detail = health.deploy_verdict("a" * 40, "b" * 40)
        self.assertEqual(level, "fail")
        self.assertIn("aaaaaaa", detail)
        self.assertIn("bbbbbbb", detail)

    def test_no_deployment_fails(self):
        self.assertEqual(health.deploy_verdict("", "b" * 40)[0], "fail")


class MediaVerdictTests(unittest.TestCase):
    def test_all_media_answering_is_ok(self):
        self.assertEqual(health.media_verdict({"a.mp4": (200, 1024)})[0], "ok")

    def test_missing_media_fails_and_names_the_file(self):
        level, detail = health.media_verdict({"a.mp4": (200, 1024), "b.mp4": (404, 0)})
        self.assertEqual(level, "fail")
        self.assertIn("b.mp4", detail)
        self.assertNotIn("a.mp4", detail)

    def test_unreachable_media_fails(self):
        self.assertEqual(health.media_verdict({"a.mp4": None})[0], "fail")


class ContentVerdictTests(unittest.TestCase):
    def test_matching_digests_are_ok(self):
        self.assertEqual(health.content_verdict("abc", "abc")[0], "ok")

    def test_different_digests_fail(self):
        self.assertEqual(health.content_verdict("abc", "def")[0], "fail")

    def test_unreachable_page_fails(self):
        self.assertEqual(health.content_verdict("abc", None)[0], "fail")


class SummaryTests(unittest.TestCase):
    def test_failures_are_listed_first(self):
        report = health.summary([
            {"check": "media", "level": "ok", "detail": "fine"},
            {"check": "deployment", "level": "fail", "detail": "behind"},
        ])
        self.assertLess(report.index("deployment"), report.index("media"))
        self.assertIn("1 fail, 0 warn, 1 ok", report)


class MediaRefsTests(unittest.TestCase):
    def test_references_are_resolved_from_each_page(self):
        refs = health.media_refs()
        self.assertTrue(refs, "no media references found; run tests from the repository root")
        for name in refs:
            self.assertTrue((Path("site") / "media" / name).exists(), f"{name} is linked but absent")

    def test_the_orphan_page_is_not_reported_as_referenced(self):
        self.assertNotIn("klon8-701cd1a9.html", health.media_refs())


if __name__ == "__main__":
    unittest.main()

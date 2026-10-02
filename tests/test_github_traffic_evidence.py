import unittest

from engine.analytics import validate_external_evidence


class GithubTrafficEvidenceTests(unittest.TestCase):
    def test_github_traffic_metrics_are_accepted(self):
        result = validate_external_evidence({
            "provider": "github_repository_traffic",
            "retrieved_at": "2026-10-02T01:57:01+00:00",
            "source_url": "https://github.com/farmmer938-lgtm/autonomous-zero-baht/graphs/traffic",
            "verification_reference": "github-traffic-14-day-dashboard-extract",
            "metrics": {
                "clones": 218,
                "unique_cloners": 101,
                "views": 5,
                "unique_visitors": 1,
            },
        })
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "VERIFIED")

    def test_github_traffic_metrics_remain_numeric_and_non_negative(self):
        result = validate_external_evidence({
            "provider": "github_repository_traffic",
            "retrieved_at": "2026-10-02T01:57:01+00:00",
            "source_url": "https://github.com/farmmer938-lgtm/autonomous-zero-baht/graphs/traffic",
            "verification_reference": "github-traffic-14-day-dashboard-extract",
            "metrics": {"clones": -1},
        })
        self.assertFalse(result["verified"])
        self.assertIn("negative_metric:clones", result["errors"])


if __name__ == "__main__":
    unittest.main()

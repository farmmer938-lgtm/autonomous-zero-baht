import unittest


from engine.analytics import empty_economic_evidence, validate_external_evidence
from engine.distribution import build_distribution_plan, dry_run_distribution, publish


class DistributionGateTests(unittest.TestCase):
    def test_gate_is_disabled_by_default(self):
        plan = build_distribution_plan([])
        self.assertFalse(plan["enabled"])
        self.assertFalse(plan["publish_automatically"])
        self.assertFalse(plan["live_publish_authorized"])
        self.assertEqual(plan["action"], "dry_run_only")
        self.assertFalse(plan["publish_performed"])

    def test_dry_run_cannot_publish(self):
        plan = dry_run_distribution(["data/content/drafts/example.json"])
        self.assertEqual(plan["provider"], "github_pages")
        self.assertFalse(plan["publish_performed"])

    def test_live_publish_is_hard_blocked(self):
        with self.assertRaises(RuntimeError):
            publish(["draft.json"])

    def test_external_evidence_requires_verifiable_provenance(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "2026-10-02T00:00:00+00:00",
            "source_url": "https://example.com/dashboard",
            "metrics": {"clicks": 12},
        })
        self.assertFalse(result["verified"])
        self.assertIn("missing_verification_reference", result["errors"])
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_empty_metrics_are_not_verified(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "2026-10-02T00:00:00+00:00",
            "source_url": "https://example.com/dashboard",
            "verification_reference": "external-record-123",
            "metrics": {},
        })
        self.assertFalse(result["verified"])
        self.assertIn("missing_metrics", result["errors"])

    def test_naive_retrieved_at_is_not_verified(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "2026-10-02T00:00:00",
            "source_url": "https://example.com/dashboard",
            "verification_reference": "external-record-123",
            "metrics": {"clicks": 1},
        })
        self.assertFalse(result["verified"])
        self.assertIn("invalid_retrieved_at", result["errors"])

    def test_negative_metrics_are_not_verified(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "2026-10-02T00:00:00+00:00",
            "source_url": "https://example.com/dashboard",
            "verification_reference": "external-record-123",
            "metrics": {"clicks": -1},
        })
        self.assertFalse(result["verified"])
        self.assertIn("negative_metric:clicks", result["errors"])

    def test_valid_external_evidence_is_structurally_verifiable(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "2026-10-02T00:00:00+00:00",
            "source_url": "https://example.com/dashboard",
            "verification_reference": "external-record-123",
            "metrics": {"impressions": 100, "clicks": 12, "conversions": 1},
        })
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "VERIFIED")

    def test_invalid_retrieved_at_is_not_verified(self):
        result = validate_external_evidence({
            "provider": "example",
            "retrieved_at": "not-a-date",
            "source_url": "https://example.com/dashboard",
            "verification_reference": "external-record-123",
            "metrics": {"clicks": 1},
        })
        self.assertFalse(result["verified"])
        self.assertIn("invalid_retrieved_at", result["errors"])

    def test_boolean_and_non_finite_metrics_are_not_verified(self):
        for value, expected_error in [
            (True, "non_numeric_metric:clicks"),
            (float("nan"), "non_finite_metric:clicks"),
            (float("inf"), "non_finite_metric:clicks"),
        ]:
            result = validate_external_evidence({
                "provider": "example",
                "retrieved_at": "2026-10-02T00:00:00+00:00",
                "source_url": "https://example.com/dashboard",
                "verification_reference": "external-record-123",
                "metrics": {"clicks": value},
            })
            self.assertFalse(result["verified"])
            self.assertIn(expected_error, result["errors"])

    def test_invalid_evidence_shape_is_not_verified(self):
        result = validate_external_evidence(None)
        self.assertFalse(result["verified"])
        self.assertEqual(result["status"], "NOT_VERIFIED")
        self.assertIn("invalid_evidence", result["errors"])

    def test_empty_economic_evidence_does_not_invent_numbers(self):
        evidence = empty_economic_evidence()
        self.assertEqual(evidence["status"], "NOT_VERIFIED")
        self.assertEqual(evidence["metrics"]["revenue"], "not_verified")
        self.assertEqual(evidence["metrics"]["cash_received"], "not_verified")


if __name__ == "__main__":
    unittest.main()

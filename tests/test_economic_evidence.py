import math
import unittest

from engine.economic_evidence import validate_economic_evidence, reconcile_economic_evidence, normalize_provider_event


class EconomicEvidenceValidatorTests(unittest.TestCase):
    def valid(self):
        return {
            "source_url": "https://provider.example/transaction/tx-123",
            "provider": "ExampleProvider",
            "retrieved_at": "2026-10-02T02:10:00+00:00",
            "verification_reference": "provider-export-20261002",
            "transaction_reference": "tx-123",
            "currency": "THB",
            "metrics": {
                "transaction_amount": 100,
                "provider_fee": 5,
                "net_revenue": 95,
            },
        }

    def test_valid_provider_transaction_is_verified(self):
        result = validate_economic_evidence(self.valid())
        self.assertTrue(result["verified"])
        self.assertEqual(result["status"], "VERIFIED")

    def test_ingestion_stays_disabled_without_authorization(self):
        from engine.economic_evidence import ingest_economic_evidence
        result = ingest_economic_evidence(self.valid())
        self.assertFalse(result["ingested"])
        self.assertEqual(result["status"], "NOT_VERIFIED")
        self.assertIn("economic_ingestion_disabled", result["errors"])

    def test_authorized_ingestion_requires_verified_evidence(self):
        from engine.economic_evidence import ingest_economic_evidence
        result = ingest_economic_evidence(self.valid(), authorized=True)
        self.assertTrue(result["ingested"])
        self.assertEqual(result["status"], "VERIFIED")

    def test_authorized_ingestion_rejects_invalid_evidence(self):
        from engine.economic_evidence import ingest_economic_evidence
        evidence = self.valid()
        evidence["metrics"]["transaction_amount"] = -1
        result = ingest_economic_evidence(evidence, authorized=True)
        self.assertFalse(result["ingested"])
        self.assertEqual(result["status"], "NOT_VERIFIED")

    def test_missing_transaction_reference_is_rejected(self):
        evidence = self.valid()
        del evidence["transaction_reference"]
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("missing_transaction_reference", result["errors"])

    def test_naive_timestamp_is_rejected(self):
        evidence = self.valid()
        evidence["retrieved_at"] = "2026-10-02T02:10:00"
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("invalid_retrieved_at", result["errors"])

    def test_unknown_metric_is_rejected(self):
        evidence = self.valid()
        evidence["metrics"]["profit_guess"] = 123
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("unknown_metrics:profit_guess", result["errors"])

    def test_negative_amount_is_rejected(self):
        evidence = self.valid()
        evidence["metrics"]["transaction_amount"] = -1
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("negative_metric:transaction_amount", result["errors"])

    def test_boolean_metric_is_rejected(self):
        evidence = self.valid()
        evidence["metrics"]["revenue"] = True
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("non_numeric_metric:revenue", result["errors"])

    def test_non_finite_metric_is_rejected(self):
        evidence = self.valid()
        evidence["metrics"]["revenue"] = math.inf
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("non_finite_metric:revenue", result["errors"])

    def test_bad_currency_is_rejected(self):
        evidence = self.valid()
        evidence["currency"] = "baht"
        result = validate_economic_evidence(evidence)
        self.assertFalse(result["verified"])
        self.assertIn("invalid_currency", result["errors"])

    def test_provider_event_is_pending_until_authoritative_evidence(self):
        result = normalize_provider_event({"action": "created", "sponsorship": {"id": "sp-1"}})
        self.assertEqual(result["status"], "PENDING_VERIFICATION")
        self.assertTrue(result["verification_required"])

    def test_synthetic_evidence_can_never_verify(self):
        result = reconcile_economic_evidence(self.valid(), external_authoritative=True, authorized=True, synthetic=True)
        self.assertEqual(result["status"], "NOT_VERIFIED")
        self.assertFalse(result["ingested"])

    def test_non_authoritative_evidence_stays_pending(self):
        result = reconcile_economic_evidence(self.valid(), external_authoritative=False, authorized=True)
        self.assertEqual(result["status"], "PENDING_VERIFICATION")
        self.assertFalse(result["ingested"])

    def test_authoritative_evidence_requires_ingestion_authorization(self):
        result = reconcile_economic_evidence(self.valid(), external_authoritative=True, authorized=False)
        self.assertEqual(result["status"], "PENDING_VERIFICATION")
        self.assertIn("economic_ingestion_disabled", result["errors"])


if __name__ == "__main__":
    unittest.main()

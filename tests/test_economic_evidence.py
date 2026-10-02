import math
import unittest

from engine.economic_evidence import validate_economic_evidence


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

if __name__ == "__main__":
    unittest.main()

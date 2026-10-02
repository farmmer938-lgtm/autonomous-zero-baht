import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from engine.learn import record_learning


def provider_evidence():
    return {
        "source_url": "https://provider.example/transactions/tx-001",
        "provider": "test-provider",
        "retrieved_at": "2026-10-02T00:00:00+00:00",
        "verification_reference": "provider-event-001",
        "transaction_reference": "tx-001",
        "currency": "USD",
        "metrics": {
            "transaction_amount": 25.0,
            "revenue": 25.0,
        },
    }


class TestEconomicLearningGate(unittest.TestCase):
    def test_default_learning_contains_no_verified_economic_evidence(self):
        with TemporaryDirectory() as tmp:
            with patch("engine.learn.ROOT", Path(tmp)):
                result = record_learning()
        self.assertEqual(result["economic_evidence"]["status"], "NOT_VERIFIED")
        self.assertFalse(result["economic_evidence"]["ingested"])

    def test_valid_evidence_stays_blocked_without_authorization(self):
        with TemporaryDirectory() as tmp:
            with patch("engine.learn.ROOT", Path(tmp)):
                result = record_learning(provider_evidence())
        self.assertEqual(result["economic_evidence"]["status"], "NOT_VERIFIED")
        self.assertFalse(result["economic_evidence"]["ingested"])
        self.assertEqual(result["economic_evidence"]["reason"], "economic_ingestion_disabled")

    def test_verified_evidence_can_enter_learning_only_when_explicitly_authorized(self):
        with TemporaryDirectory() as tmp:
            with patch("engine.learn.ROOT", Path(tmp)):
                result = record_learning(provider_evidence(), economic_authorized=True)
        self.assertEqual(result["economic_evidence"]["status"], "VERIFIED")
        self.assertTrue(result["economic_evidence"]["ingested"])
        self.assertEqual(result["economic_evidence"]["metrics"]["revenue"], 25.0)

    def test_invalid_evidence_never_enters_learning_even_when_authorized(self):
        evidence = provider_evidence()
        evidence["metrics"]["revenue"] = -1
        with TemporaryDirectory() as tmp:
            with patch("engine.learn.ROOT", Path(tmp)):
                result = record_learning(evidence, economic_authorized=True)
        self.assertEqual(result["economic_evidence"]["status"], "NOT_VERIFIED")
        self.assertFalse(result["economic_evidence"]["ingested"])


if __name__ == "__main__":
    unittest.main()

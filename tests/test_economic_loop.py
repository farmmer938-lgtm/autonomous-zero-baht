import unittest
from pathlib import Path
from engine.economic_loop import GateStatus, LoopState, build_loop_state, load_runtime_gates, validate_provider_event, build_activation_readiness, build_human_gate_checklist

class EconomicLoopTests(unittest.TestCase):
    def test_runtime_gates_are_loaded_from_safe_config(self):
        gates = load_runtime_gates(Path(__file__).resolve().parents[1])
        self.assertFalse(gates["distribution_enabled"])
        self.assertFalse(gates["live_publish_authorized"])
        self.assertFalse(gates["economic_verification_authorized"])

    def test_disabled_distribution_stays_pending(self):
        state=build_loop_state(distribution_enabled=False,live_publish_authorized=False)
        self.assertEqual(state["status"],GateStatus.PENDING.value)
        self.assertEqual(state["state"],LoopState.PUBLISH.value)
    def test_validation_failure_blocks_loop(self):
        state=build_loop_state(distribution_enabled=True,live_publish_authorized=True,
                               economic_evidence_status="VERIFIED",validation_failures=1)
        self.assertEqual(state["status"],GateStatus.BLOCKED.value)
    def test_verified_prerequisites_return_to_research(self):
        state=build_loop_state(distribution_enabled=True,live_publish_authorized=True,
                               economic_evidence_status="VERIFIED")
        self.assertEqual(state["status"],GateStatus.VERIFIED.value)
        self.assertEqual(state["next"],LoopState.RESEARCH.value)
    def test_provider_event_never_self_verifies(self):
        result=validate_provider_event({"action":"created","sponsorship":{"id":"example-id"}})
        self.assertEqual(result["status"],GateStatus.PENDING.value)
        self.assertTrue(result["verification_required"])
    def test_invalid_provider_event(self):
        self.assertEqual(validate_provider_event({})["status"],GateStatus.NOT_VERIFIED.value)

    def test_provider_event_without_transaction_reference_is_not_verified(self):
        result = validate_provider_event({"action": "created", "sponsorship": {}})
        self.assertEqual(result["status"], GateStatus.NOT_VERIFIED.value)
        self.assertIn("missing_transaction_reference", result["errors"])


    def test_activation_readiness_reports_missing_gates_without_mutation(self):
        gates = load_runtime_gates(Path(__file__).resolve().parents[1])
        result = build_activation_readiness(gates)
        self.assertEqual(result["status"], "PENDING")
        self.assertTrue(result["missing_gates"])
        self.assertFalse(result["activation_changes_applied"])

    def test_human_gate_checklist_is_pending_without_authorization(self):
        result = build_human_gate_checklist({
            "distribution_enabled": False,
            "live_publish_authorized": False,
            "economic_verification_authorized": False,
        })
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(result["checks"]["provider_account_setup"], "NOT_VERIFIED")
        self.assertEqual(result["checks"]["kyc_tax_bank_2fa_if_required"], "NOT_VERIFIED")
        self.assertEqual(result["checks"]["live_publish_authorization"], "PENDING")
        self.assertFalse(result["authorization_changes_applied"])
        self.assertEqual(result["verification_basis"]["provider_account_setup"], "external_provider_authoritative_evidence_required")
        self.assertEqual(result["verification_basis"]["live_publish_authorization"], "runtime_config_gate")

    def test_human_gate_checklist_stays_pending_when_only_runtime_gates_are_true(self):
        result = build_human_gate_checklist({
            "distribution_enabled": True,
            "live_publish_authorized": True,
            "economic_verification_authorized": True,
        })
        self.assertEqual(result["status"], "PENDING")
        self.assertEqual(result["checks"]["live_publish_authorization"], "VERIFIED")
        self.assertEqual(result["checks"]["distribution_runtime_enabled"], "VERIFIED")
        self.assertEqual(result["checks"]["provider_account_setup"], "NOT_VERIFIED")
        self.assertFalse(result["authorization_changes_applied"])


    def test_activation_readiness_is_ready_only_when_all_gates_are_true(self):
        result = build_activation_readiness({
            "distribution_enabled": True,
            "live_publish_authorized": True,
            "economic_verification_authorized": True,
        })
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["missing_gates"], [])


if __name__=="__main__": unittest.main()

import unittest
from engine.economic_loop import GateStatus, LoopState, build_loop_state, validate_provider_event

class EconomicLoopTests(unittest.TestCase):
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

if __name__=="__main__": unittest.main()

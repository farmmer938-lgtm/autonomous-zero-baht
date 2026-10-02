import unittest
import tempfile
import json
from pathlib import Path
from engine.optimize import optimize

class OptimizeTests(unittest.TestCase):
    def test_failures_do_not_scale(self):
        with tempfile.TemporaryDirectory() as tmp:
            import engine.optimize as module
            old = module.ROOT
            module.ROOT = Path(tmp)
            try:
                result = optimize({"research_items": 3, "drafts_created": 2, "validation_failures": 1}, {"economic_evidence": {"status": "NOT_VERIFIED"}})
                self.assertEqual(result["action"], "reduce_or_hold_draft_generation_and_fix_validation")
                self.assertFalse(result["live_publish_changes_allowed"])
                self.assertFalse(result["economic_changes_allowed"])
                self.assertTrue((Path(tmp) / "data/analytics/optimization.json").exists())
            finally:
                module.ROOT = old

    def test_healthy_run_continues_safe_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            import engine.optimize as module
            old = module.ROOT
            module.ROOT = Path(tmp)
            try:
                result = optimize({"research_items": 4, "drafts_created": 2, "validation_failures": 0}, {"economic_evidence": {"status": "NOT_VERIFIED"}})
                self.assertEqual(result["action"], "continue_current_safe_cycle")
                self.assertEqual(result["actual_outcome"]["economic_status"], "NOT_VERIFIED")
            finally:
                module.ROOT = old

if __name__ == "__main__":
    unittest.main()

"""Phase A: a Pages deploy may only follow a green upstream run on main.

The rule lives in `tools/af_deploy_gate.py`; these tests pin both the rule and the YAML
that has to enforce it, because a gate that silently disappears looks exactly like a gate
that always passes.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_deploy_gate as gate  # noqa: E402

import yaml  # noqa: E402

PAGES = Path(".github/workflows/pages.yml")
NAME = gate.UPSTREAM_ALLOWLIST[0]


class DecisionTests(unittest.TestCase):
    def test_a_green_upstream_on_main_deploys(self):
        deploy, reason = gate.should_deploy("workflow_run", "success", "main", NAME)
        self.assertTrue(deploy, reason)

    def test_a_failed_upstream_does_not_deploy(self):
        deploy, reason = gate.should_deploy("workflow_run", "failure", "main", NAME)
        self.assertFalse(deploy)
        self.assertIn("failure", reason)

    def test_a_cancelled_upstream_does_not_deploy(self):
        self.assertFalse(gate.should_deploy("workflow_run", "cancelled", "main", NAME)[0])

    def test_a_timed_out_upstream_does_not_deploy(self):
        self.assertFalse(gate.should_deploy("workflow_run", "timed_out", "main", NAME)[0])

    def test_a_green_upstream_on_another_branch_does_not_deploy(self):
        deploy, reason = gate.should_deploy("workflow_run", "success", "feature/x", NAME)
        self.assertFalse(deploy)
        self.assertIn("feature/x", reason)

    def test_an_unlisted_upstream_does_not_deploy(self):
        self.assertFalse(gate.should_deploy("workflow_run", "success", "main", "Some Other")[0])

    def test_missing_fields_do_not_deploy(self):
        self.assertFalse(gate.should_deploy("workflow_run", None, None, None)[0])

    def test_explicit_triggers_always_deploy(self):
        for event in ("push", "workflow_dispatch", "schedule"):
            deploy, reason = gate.should_deploy(event)
            self.assertTrue(deploy, f"{event}: {reason}")


class WorkflowWiringTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(PAGES.read_text(encoding="utf-8"))
        self.deploy = self.workflow["jobs"]["deploy"]

    def test_the_job_is_gated_on_conclusion_and_branch(self):
        condition = " ".join(str(self.deploy.get("if", "")).split())
        self.assertIn("github.event.workflow_run.conclusion == 'success'", condition)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", condition)
        self.assertIn("github.event_name != 'workflow_run'", condition)

    def test_the_allowlist_matches_the_workflows_that_trigger_a_deploy(self):
        listed = tuple(self.workflow[True]["workflow_run"]["workflows"])
        self.assertEqual(listed, gate.UPSTREAM_ALLOWLIST)

    def test_the_trigger_is_checked_in_code_before_anything_is_published(self):
        steps = self.deploy["steps"]
        names = [s.get("name") for s in steps]
        self.assertIn("Check the trigger", names)
        check = steps[names.index("Check the trigger")]
        self.assertEqual(check["run"], "python tools/af_deploy_gate.py")
        self.assertEqual(check["if"], "github.event_name == 'workflow_run'")
        passed = " ".join(check["env"].values())
        for upstream in ("conclusion", "head_branch", "name"):
            self.assertIn(f"github.event.workflow_run.{upstream}", passed)


if __name__ == "__main__":
    unittest.main()

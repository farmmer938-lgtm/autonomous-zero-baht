"""Phase A: a Pages deploy may only follow a green upstream run on main.

The rule lives in `tools/af_deploy_gate.py`; these tests pin both the rule and the YAML
that has to enforce it, because a gate that silently disappears looks exactly like a gate
that always passes.

CI runs the suite on a bare Python with no third-party packages, so the workflow is read as
text (like `test_workflow_safety.py`) instead of being parsed with a YAML library.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_deploy_gate as gate  # noqa: E402

PAGES_TEXT = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
NAME = gate.UPSTREAM_ALLOWLIST[0]


def _squash(text):
    return " ".join(text.split())


def _step(name):
    """The text of one step, from its `- name:` line to the next step."""
    start = PAGES_TEXT.index(f"- name: {name}")
    rest = PAGES_TEXT[start + 1:]
    end = rest.find("\n      - ")
    return _squash(rest if end == -1 else rest[:end])


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
    def test_the_job_is_gated_on_conclusion_and_branch(self):
        text = _squash(PAGES_TEXT)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn("github.event_name != 'workflow_run'", text)

    def test_the_allowlist_matches_the_workflows_that_trigger_a_deploy(self):
        block = PAGES_TEXT[PAGES_TEXT.index("workflow_run:"):]
        block = block[:block.index("types:")]
        listed = tuple(re.findall(r"^\s+- (.+)$", block, re.MULTILINE))
        self.assertEqual(listed, gate.UPSTREAM_ALLOWLIST)

    def test_the_trigger_is_checked_in_code_before_anything_is_published(self):
        step = _step("Check the trigger")
        self.assertIn("run: python tools/af_deploy_gate.py", step)
        self.assertIn("if: github.event_name == 'workflow_run'", step)
        for upstream in ("conclusion", "head_branch", "name"):
            self.assertIn(f"github.event.workflow_run.{upstream}", step)

    def test_the_check_runs_before_the_upload(self):
        self.assertLess(PAGES_TEXT.index("- name: Check the trigger"),
                        PAGES_TEXT.index("- name: Upload safe static status page"))


if __name__ == "__main__":
    unittest.main()

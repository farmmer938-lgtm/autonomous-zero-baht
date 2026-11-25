"""Phase C: a rollback may only redeploy a commit that main actually shipped from.

The workflow is manual-only and defaults to a dry run; these tests pin the decision rule and
the wiring that keeps the deploy behind it.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_rollback_check as rb  # noqa: E402

MAIN = "9fe899a4e3caeb731c63cb0612dd85839d32dfa8"
OLD = "e5d61bf9cb441635885baec2f19a0fb3033192e1"
WORKFLOW = Path(".github/workflows/rollback.yml").read_text(encoding="utf-8")


class ValidateTests(unittest.TestCase):
    def test_an_ancestor_of_main_is_allowed(self):
        ok, reason = rb.validate(OLD, MAIN, True)
        self.assertTrue(ok, reason)

    def test_a_short_sha_is_refused(self):
        ok, reason = rb.validate("e5d61bf", MAIN, True)
        self.assertFalse(ok)
        self.assertIn("40-character", reason)

    def test_a_non_hex_sha_is_refused(self):
        self.assertFalse(rb.validate("z" * 40, MAIN, True)[0])

    def test_an_empty_target_is_refused(self):
        self.assertFalse(rb.validate("", MAIN, True)[0])

    def test_the_current_head_is_refused(self):
        ok, reason = rb.validate(MAIN, MAIN, True)
        self.assertFalse(ok)
        self.assertIn("already the head of main", reason)

    def test_a_commit_outside_main_is_refused(self):
        ok, reason = rb.validate(OLD, MAIN, False)
        self.assertFalse(ok)
        self.assertIn("not an ancestor", reason)

    def test_uppercase_input_is_accepted(self):
        self.assertTrue(rb.validate(OLD.upper(), MAIN, True)[0])


class WorkflowWiringTests(unittest.TestCase):
    def test_it_is_manual_only(self):
        triggers = re.search(r"^on:\n(.*?)^\S", WORKFLOW, re.S | re.M).group(1)
        self.assertIn("workflow_dispatch:", triggers)
        for automatic in ("push:", "schedule:", "workflow_run:", "pull_request:"):
            self.assertNotIn(automatic, triggers)

    def test_it_needs_a_target_sha(self):
        self.assertIn("target_sha:", WORKFLOW)
        self.assertRegex(WORKFLOW, r"target_sha:\n\s+description:.*\n\s+required: true")

    def test_a_dry_run_is_the_default(self):
        self.assertRegex(WORKFLOW, r"dry_run:\n(?:.*\n)*?\s+default: true")
        self.assertIn("if: inputs.dry_run == false", WORKFLOW)

    def test_it_checks_ancestry_before_deploying(self):
        self.assertIn("fetch-depth: 0", WORKFLOW)
        self.assertIn("python tools/af_rollback_check.py", WORKFLOW)
        self.assertIn("needs: check", WORKFLOW)

    def test_it_prints_both_shas(self):
        self.assertIn("current main: $(git rev-parse origin/main)", WORKFLOW)
        self.assertIn("requested target: ${TARGET_SHA}", WORKFLOW)

    def test_it_shares_the_pages_concurrency_group(self):
        self.assertRegex(WORKFLOW, r"concurrency:\n\s+group: pages")

    def test_it_deploys_the_target_tree_not_main(self):
        self.assertIn("ref: ${{ needs.check.outputs.target_sha }}", WORKFLOW)


if __name__ == "__main__":
    unittest.main()

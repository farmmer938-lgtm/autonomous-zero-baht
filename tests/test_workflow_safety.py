"""Guards for the workflow files themselves.

A stale branch once carried a workflow that base64-encoded `toJSON(secrets)` into the run
log of a public repository, and every `uses:` was a mutable tag. Both are cheap to check,
so the tests below fail the build instead of relying on someone noticing.
"""
import re
import unittest
from pathlib import Path

WORKFLOWS = sorted(Path(".github/workflows").glob("*.yml"))
USES = re.compile(r"^\s*uses:\s*(\S+)", re.MULTILINE)


class WorkflowSafetyTests(unittest.TestCase):
    def test_workflow_files_exist(self):
        self.assertTrue(WORKFLOWS, "no workflow files found; run tests from the repository root")

    def test_no_workflow_dumps_secrets_or_variables(self):
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            for needle in ("toJSON(secrets)", "toJSON(vars)", "printenv", "env |"):
                self.assertNotIn(needle, text, f"{path} can leak secrets via {needle!r}")

    def test_no_workflow_uses_pull_request_target(self):
        for path in WORKFLOWS:
            self.assertNotIn("pull_request_target", path.read_text(encoding="utf-8"),
                             f"{path} runs fork code with write permissions")

    def test_every_action_is_pinned_to_a_commit_sha(self):
        for path in WORKFLOWS:
            for ref in USES.findall(path.read_text(encoding="utf-8")):
                if ref.startswith("./"):
                    continue
                _, _, version = ref.partition("@")
                self.assertRegex(version, r"^[0-9a-f]{40}$",
                                 f"{path} uses mutable ref {ref!r}; pin a commit SHA")

    def test_workflow_run_never_checks_out_the_triggering_run(self):
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            if "workflow_run" not in text:
                continue
            self.assertNotIn("workflow_run.head_sha", text,
                             f"{path} would execute code from the run that triggered it")

    def test_no_step_silently_swallows_failure(self):
        for path in WORKFLOWS:
            for line in path.read_text(encoding="utf-8").splitlines():
                if "|| true" in line:
                    self.assertIn("git pull", line,
                                  f"{path}: '|| true' hides failures except on the merge line: {line.strip()}")


if __name__ == "__main__":
    unittest.main()

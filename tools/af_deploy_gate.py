"""Decide whether a Pages deploy may run, and say why.

`workflow_run` fires for every completion of an allowlisted workflow, including the ones
that failed or were cancelled, and including runs on a branch that is not `main`. Deploying
after those publishes nothing new at best and publishes a stale tree at worst, so the
decision lives here where it can be tested instead of inside a YAML expression nobody runs.

Exit code is the answer: 0 deploy, 1 refuse. The reason always goes to stdout.
"""
import os
import sys

# Must stay equal to `.github/workflows/pages.yml` -> `on.workflow_run.workflows`; a test
# asserts it, because a name that drifts here silently stops guarding anything.
UPSTREAM_ALLOWLIST = (
    "Zero-Baht Research and Drafts",
    "AF Verified Facts (durable, no secrets)",
    "AF Public Watch (free, no secrets)",
    "AF Revenue Verify (free, no secrets)",
)


def should_deploy(event_name, conclusion=None, head_branch=None, upstream_name=None):
    """Return (deploy, reason) for one trigger."""
    if event_name != "workflow_run":
        return True, f"{event_name or 'unknown'} is an explicit trigger"
    if conclusion != "success":
        return False, f"upstream conclusion is {conclusion!r}, not 'success'"
    if head_branch != "main":
        return False, f"upstream ran on {head_branch!r}, not 'main'"
    if upstream_name not in UPSTREAM_ALLOWLIST:
        return False, f"upstream {upstream_name!r} is not in the allowlist"
    return True, f"upstream {upstream_name!r} succeeded on main"


def main():
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    deploy, reason = should_deploy(
        event_name,
        os.environ.get("UPSTREAM_CONCLUSION"),
        os.environ.get("UPSTREAM_BRANCH"),
        os.environ.get("UPSTREAM_NAME"),
    )
    print(("deploy: " if deploy else "refuse: ") + reason)
    return 0 if deploy else 1


if __name__ == "__main__":
    sys.exit(main())

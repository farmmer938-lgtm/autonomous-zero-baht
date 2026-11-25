#!/usr/bin/env python3
"""Decide whether a commit may be redeployed to Pages as a rollback.

A rollback publishes an older tree over the live site, so the target is checked before
anything is uploaded: it must be a full SHA, it must be an ancestor of `main` (otherwise it
is not a state the site ever shipped from), and it must not already be what is deployed.

Exit code: 0 the target is usable, 1 refused. The reason is always printed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def validate(target, main_sha, is_ancestor):
    """Return (ok, reason). `is_ancestor` is the answer to `git merge-base --is-ancestor`."""
    target = (target or "").strip().lower()
    main_sha = (main_sha or "").strip().lower()
    if not SHA_RE.match(target):
        return False, f"target {target!r} is not a full 40-character commit SHA"
    if target == main_sha:
        return False, "target is already the head of main, so this is not a rollback"
    if not is_ancestor:
        return False, "target is not an ancestor of main"
    return True, f"{target[:7]} is an ancestor of main ({main_sha[:7]})"


def git(*args):
    return subprocess.run(("git",) + args, capture_output=True, text=True)


def check(target, ref="origin/main"):
    head = git("rev-parse", ref)
    if head.returncode != 0:
        return False, f"cannot resolve {ref}", {}
    main_sha = head.stdout.strip()
    exists = git("cat-file", "-e", f"{target}^{{commit}}").returncode == 0
    if not exists:
        return False, f"commit {target} does not exist in this clone", {}
    ancestor = git("merge-base", "--is-ancestor", target, ref).returncode == 0
    ok, reason = validate(target, main_sha, ancestor)
    info = {"main_sha": main_sha, "target_sha": target.lower()}
    subject = git("log", "-1", "--format=%s (%ci)", target)
    if subject.returncode == 0:
        info["target_subject"] = subject.stdout.strip()
    return ok, reason, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target_sha")
    ap.add_argument("--ref", default="origin/main")
    a = ap.parse_args()
    ok, reason, info = check(a.target_sha, a.ref)
    for key in ("main_sha", "target_sha", "target_subject"):
        if info.get(key):
            print(f"{key}: {info[key]}")
    print(("allow: " if ok else "refuse: ") + reason)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

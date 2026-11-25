# Rolling the site back

The live site is a Pages deployment of `main`. A rollback republishes an **older commit**
over it. It is a stopgap: the next scheduled `pages.yml` run (every 6 hours, plus every push
to main) publishes `main` again. Making a rollback permanent means reverting on `main`.

## When to use it

- `main` merged something that broke the site and a fix will take longer than a few minutes.
- A deploy is serving a tree that is not what `main` contains.

Do not use it to "test" a deploy. The workflow defaults to a dry run for that reason.

## Run it

```bash
# 1. dry run: prints main, the target, and every commit that would stop being deployed
gh workflow run rollback.yml -f target_sha=<40-hex-sha> -f dry_run=true

# 2. read the log of the `check` job, then deploy
gh workflow run rollback.yml -f target_sha=<40-hex-sha> -f dry_run=false
```

`target_sha` must be a **full 40-character** SHA that is an ancestor of `main`. The workflow
refuses anything else, and refuses the current head of `main` (that is not a rollback).

Find a candidate:

```bash
git log --oneline -20 origin/main
```

## What the check job guarantees

| condition | result |
|---|---|
| SHA is 40 hex characters | otherwise refuse |
| commit exists in the clone | otherwise refuse |
| commit is an ancestor of `main` | otherwise refuse |
| commit is not the current head | otherwise refuse |

The job prints `current main:`, `requested target:`, and the list of commits that would
stop being deployed, so the log is the record of what changed.

## Verify afterwards

```bash
# the deployment that is live right now
gh api repos/farmmer938-lgtm/autonomous-zero-baht/deployments \
  --jq '.[0] | "\(.sha[0:7]) \(.created_at)"'

# the page really changed (cache-busted)
curl -s -H 'Cache-Control: no-cache' \
  https://farmmer938-lgtm.github.io/autonomous-zero-baht/status.html | head -5

# the health report agrees that the site is serving what was deployed
gh workflow run pages_health.yml
```

`tools/af_pages_health.py` compares the deployed SHA with `main`; after an intentional
rollback it will report `deployment: FAIL` until `main` is reverted. That is correct: the
site is knowingly behind `main`.

## Making it permanent

```bash
git revert --no-edit <bad-sha>       # on a branch, then a PR, then merge
```

Merge the revert and the normal `pages.yml` push deploy publishes it.

## Rollback of a rollback

Re-run the workflow with the SHA you rolled back from — it is an ancestor of `main` too.

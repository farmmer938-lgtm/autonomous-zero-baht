"""Report the health of the published site: deployment, storage, media, freshness.

Every check answers a question that has already cost a deploy at least once:

* is the live site the commit that `main` points at (a red deploy leaves the old site up);
* is the artifact quota about to swallow the next deploy silently;
* does every media file a page links to still answer;
* does the live status page byte-match the one in the repository.

Read-only: it needs `contents: read` and `actions: read`, writes no repository content,
and exits non-zero only for FAIL findings so a red run means something needs a human.
"""
import hashlib
import json
import os
import posixpath
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path("site")
LINK = re.compile(r"""(?:src|href|poster)\s*=\s*["']([^"'#?]+)""")
DEFAULT_SITE_URL = "https://farmmer938-lgtm.github.io/autonomous-zero-baht"
WARN_BYTES = 200 * 1024 * 1024
FAIL_BYTES = 450 * 1024 * 1024


def artifact_verdict(total_bytes):
    """Quota is 500 MB and GitHub does not warn before an upload stops being kept."""
    if total_bytes >= FAIL_BYTES:
        return "fail", f"{total_bytes / 1048576:.0f} MB of 500 MB used; the next deploy may not be kept"
    if total_bytes >= WARN_BYTES:
        return "warn", f"{total_bytes / 1048576:.0f} MB of 500 MB used"
    return "ok", f"{total_bytes / 1048576:.0f} MB of 500 MB used"


def deploy_verdict(deployed_sha, head_sha):
    """A failed deploy leaves the previous site serving, so the site lags `main`."""
    if not deployed_sha:
        return "fail", "no Pages deployment found"
    if not head_sha:
        return "fail", "cannot read the head of main"
    if deployed_sha != head_sha:
        return "fail", f"live site is {deployed_sha[:7]}, main is {head_sha[:7]}"
    return "ok", f"live site is main ({head_sha[:7]})"


def media_refs(site_dir=SITE):
    """Media files that a published page links to, resolved from that page's directory."""
    root = Path(site_dir)
    names = set()
    for page in sorted(root.rglob("*.html")):
        base = page.parent.relative_to(root).as_posix()
        for target in LINK.findall(page.read_text(encoding="utf-8", errors="replace")):
            if target.startswith(("http://", "https://", "//", "mailto:", "data:")):
                continue
            resolved = posixpath.normpath(posixpath.join(base, target))
            if resolved.startswith("media/"):
                names.add(resolved[len("media/"):])
    return sorted(names)


def media_verdict(results):
    """`results` maps a media file name to (status_code, size) or None when unreachable."""
    broken = [f"{name} ({'unreachable' if r is None else r[0]})" for name, r in sorted(results.items())
              if r is None or r[0] != 200 or not r[1]]
    if broken:
        return "fail", "broken media: " + ", ".join(broken)
    return "ok", f"{len(results)} media file(s) answer"


def content_verdict(local_digest, live_digest):
    if live_digest is None:
        return "fail", "live status.html is unreachable"
    if local_digest != live_digest:
        return "fail", "live status.html differs from the repository copy"
    return "ok", "live status.html matches the repository"


def summary(findings):
    """Markdown for the job summary; FAIL first so it is the first thing read."""
    order = {"fail": 0, "warn": 1, "ok": 2}
    rows = sorted(findings, key=lambda f: order[f["level"]])
    icon = {"fail": "FAIL", "warn": "WARN", "ok": "ok"}
    lines = ["| check | result | detail |", "|---|---|---|"]
    lines += [f"| {f['check']} | {icon[f['level']]} | {f['detail']} |" for f in rows]
    counts = {k: sum(1 for f in findings if f["level"] == k) for k in ("fail", "warn", "ok")}
    lines.append("")
    lines.append(f"{counts['fail']} fail, {counts['warn']} warn, {counts['ok']} ok")
    return "\n".join(lines)


def _get(url, token, method="GET", raw=False):
    request = urllib.request.Request(url, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "af-pages-health")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return response.status, (body if raw else json.loads(body or b"{}"))
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError, TimeoutError):
        return None, None


def collect(repo, token, site_url, site_dir=SITE):
    findings = []

    _, head = _get(f"https://api.github.com/repos/{repo}/commits/main", token)
    head_sha = (head or {}).get("sha", "")

    _, deployments = _get(
        f"https://api.github.com/repos/{repo}/deployments?environment=github-pages&per_page=1", token)
    deployed_sha = (deployments or [{}])[0].get("sha", "") if isinstance(deployments, list) else ""
    level, detail = deploy_verdict(deployed_sha, head_sha)
    findings.append({"check": "deployment", "level": level, "detail": detail})

    _, artifacts = _get(f"https://api.github.com/repos/{repo}/actions/artifacts?per_page=100", token)
    total = sum(a.get("size_in_bytes", 0) for a in (artifacts or {}).get("artifacts", []))
    level, detail = artifact_verdict(total)
    findings.append({"check": "artifact storage", "level": level, "detail": detail})

    results = {}
    for name in media_refs(site_dir):
        local = Path(site_dir) / "media" / name
        if not local.exists():
            results[name] = None
            continue
        status, body = _get(f"{site_url}/media/{name}", token, raw=True)
        results[name] = (status, len(body or b""))
    level, detail = media_verdict(results)
    findings.append({"check": "media", "level": level, "detail": detail})

    local_status = Path(site_dir) / "status.html"
    local_digest = hashlib.sha256(local_status.read_bytes()).hexdigest() if local_status.exists() else None
    status, body = _get(f"{site_url}/status.html", token, raw=True)
    live_digest = hashlib.sha256(body).hexdigest() if status == 200 and body else None
    level, detail = content_verdict(local_digest, live_digest)
    findings.append({"check": "content", "level": level, "detail": detail})
    return findings


def main():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    site_url = (os.environ.get("AF_SITE_URL") or DEFAULT_SITE_URL).rstrip("/")
    if not (repo and token):
        print("GITHUB_REPOSITORY and GITHUB_TOKEN are required", file=sys.stderr)
        return 2

    findings = collect(repo, token, site_url)
    report = summary(findings)
    print(report)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        Path(step_summary).write_text(report + "\n", encoding="utf-8")
    return 1 if any(f["level"] == "fail" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())

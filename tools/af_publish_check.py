#!/usr/bin/env python3
"""Did the page actually go live? That is all this measures.

HTTP 200 is evidence of publication, never of an audience. The result is written to
data/published.json as `live`, and `reach` in the funnel stays null regardless — a page that
answers 200 to a robot has not been read by a human.

Usage:
  python3 tools/af_publish_check.py            # check and print
  python3 tools/af_publish_check.py --write
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht/"
OUT = Path("data/published.json")
PATHS = ["audit/", "audit/e2/", "audit/cases/",
         "audit/guides/check-a-base-token.html", "audit/guides/mint-authority.html",
         "audit/guides/scanner-vs-evidence.html",
         "store.html", "reviews.html", "sitemap.xml", "robots.txt"]


def head(url, timeout=15):
    req = urllib.request.Request(url, method="HEAD", headers={"user-agent": "af-publish-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def summarise(results):
    """Pure: [(path, status)] -> the counts the funnel needs."""
    live = [p for p, s in results if s == 200]
    return {
        "published": len(live),
        "attempted": len(results),
        "live_paths": live,
        "dead_paths": [p for p, s in results if s != 200],
        "note": "200 means the file is served. It is not a reader, and it is not reach.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    results = []
    for path in PATHS:
        url = BASE + path
        results.append((path, head(url)))
        print(f"{results[-1][1]}  {path}")
    out = {"schema": "af.published.v1", "at": datetime.now(timezone.utc).isoformat(),
           **summarise(results), "base": BASE}
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", OUT, "published =", out["published"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

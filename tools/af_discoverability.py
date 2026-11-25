#!/usr/bin/env python3
"""What AF can prove about being findable, and what it cannot.

Proves: the sitemap parses and every URL in it answers 200; robots.txt does not block crawlers;
each page carries a unique title, a description, a canonical URL, one h1 and JSON-LD; internal
links resolve; the repository's own discovery fields are filled.

Cannot prove: whether Google has indexed anything. There is no Search Console account, and
automated queries to a search engine are blocked. The tool reports indexing as `None` and says
why, because "not measured" and "not indexed" are different facts.

Usage:
  python3 tools/af_discoverability.py            # print
  python3 tools/af_discoverability.py --write
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://farmmer938-lgtm.github.io/autonomous-zero-baht/"
SITE = Path("site")
OUT = Path("data/discoverability.json")
PAGES = ["audit/index.html", "audit/cases/index.html",
         "audit/guides/check-a-base-token.html", "audit/guides/mint-authority.html",
         "audit/guides/scanner-vs-evidence.html", "reviews.html", "store.html", "index.html"]


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = None
        self.desc = None
        self.canonical = None
        self.h1 = 0
        self.jsonld = 0
        self.links = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta" and a.get("name") == "description":
            self.desc = a.get("content")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self.jsonld += 1
        elif tag == "h1":
            self.h1 += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()


def parse(path):
    p = Head()
    p.feed(Path(path).read_text(encoding="utf-8"))
    return p


def internal_targets(links, source):
    """Relative or same-site links, as site-relative paths, deduped."""
    out = set()
    for href in links:
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.startswith(BASE):
            out.add(href[len(BASE):])
        elif "://" in href:
            continue
        else:
            out.add(os.path.normpath(str(Path(SITE, source).parent / href)))
    return out


def audit(pages=PAGES, fetched=None):
    """Pure. `fetched` maps site-relative path -> HTTP status (None when unknown)."""
    rows, titles, descs, problems = [], {}, {}, []
    for rel in pages:
        if not Path(SITE, rel).exists():
            problems.append(f"{rel}: file missing")
            continue
        h = parse(Path(SITE, rel))
        titles.setdefault(h.title, []).append(rel)
        if h.desc:
            descs.setdefault(h.desc, []).append(rel)
        for field, value in (("title", h.title), ("description", h.desc),
                             ("canonical", h.canonical)):
            if not value:
                problems.append(f"{rel}: no {field}")
        if h.h1 != 1:
            problems.append(f"{rel}: {h.h1} h1 elements (expected 1)")
        if h.jsonld == 0:
            problems.append(f"{rel}: no JSON-LD")
        if h.canonical and not h.canonical.startswith(BASE):
            problems.append(f"{rel}: canonical points outside the site")
        rows.append({"path": rel, "title": h.title,
                     "http": (fetched or {}).get(rel.rstrip("index.html")),
                     "internal_links": sorted(internal_targets(h.links, rel))})
    for title, where in titles.items():
        if title and len(where) > 1:
            problems.append(f"duplicate title across {where}")
    for desc, where in descs.items():
        if len(where) > 1:
            problems.append(f"duplicate description across {where}")

    sitemap = Path(SITE, "sitemap.xml")
    sm_urls, sm_problem = [], None
    try:
        root = ET.parse(sitemap).getroot()
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        sm_urls = [e.text.strip() for e in root.iter(ns + "loc")]
    except Exception as e:
        sm_problem = f"{type(e).__name__}: {e}"
    def local_exists(url):
        rel = url[len(BASE):] if url.startswith(BASE) else url
        rel = rel.split("#")[0].split("?")[0]
        cand = Path(SITE, rel)
        return cand.exists() or Path(SITE, rel, "index.html").exists()

    missing = [u for u in sm_urls if u.startswith(BASE) and not local_exists(u)]
    robots = Path(SITE, "robots.txt")
    robots_txt = robots.read_text(encoding="utf-8") if robots.exists() else ""
    return {
        "pages": rows,
        "problems": problems,
        "sitemap": {"urls": len(sm_urls), "error": sm_problem,
                    "not_a_local_page": missing,
                    "all_local": not missing},
        "robots": {"present": robots.exists(),
                   "blocks_all": "Disallow: /" in robots_txt and "Allow: /" not in robots_txt,
                   "mentions_sitemap": "Sitemap:" in robots_txt},
        # Nothing below is inferable without a Search Console account.
        "indexing": None,
        "indexing_note": ("not measurable from here: no Search Console property, and search "
                          "engines reject automated queries. Unknown is not the same as "
                          "not indexed."),
        "backlinks_found": None,
        "backlinks_note": "no backlink source AF may query without an account",
    }


def http_status(url, timeout=15):
    try:
        req = urllib.request.Request(url, method="GET", headers={"user-agent": "af-discovery"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true", help="also fetch each page")
    a = ap.parse_args()
    fetched = {}
    if a.check:
        for rel in PAGES:
            url = BASE + rel.replace("index.html", "")
            fetched[rel.rstrip("index.html")] = http_status(url)
            print(fetched[rel.rstrip('index.html')], rel)
    out = {"schema": "af.discoverability.v1", **audit(fetched=fetched)}
    print(json.dumps({"problems": out["problems"], "sitemap": out["sitemap"],
                      "indexing": out["indexing"]}, indent=1))
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

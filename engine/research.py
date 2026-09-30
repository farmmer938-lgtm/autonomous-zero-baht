import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from .logger import log_event

ROOT = Path(__file__).resolve().parents[1]

def _text(element, names):
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""

def _fetch_feed(url, user_agent, limit):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=12) as response:
        payload = response.read(2_000_000)
    root = ET.fromstring(payload)
    items = root.findall(".//item")
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//atom:entry", ns)
        results = []
        for item in items[:limit]:
            title = _text(item, ["{http://www.w3.org/2005/Atom}title"])
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.attrib.get("href", "") if link_el is not None else ""
            summary = _text(item, ["{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"])
            results.append({"title": title, "url": link, "summary": re.sub(r"<[^>]+>", " ", summary)[:1000], "source": url})
        return results
    results = []
    for item in items[:limit]:
        title = _text(item, ["title"])
        link = _text(item, ["link"])
        summary = _text(item, ["description", "summary", "content:encoded"])
        results.append({"title": title, "url": link, "summary": re.sub(r"<[^>]+>", " ", summary)[:1000], "source": url})
    return results

def _load_seed_data(limit):
    path = ROOT / "data" / "research" / "seed.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        log_event("research_seed_failed", error=type(exc).__name__, detail=str(exc)[:250])
        return []

def run_research(config):
    all_items = []
    successful_feeds = 0
    for feed in config.get("rss_feeds", []):
        try:
            items = _fetch_feed(feed, config.get("user_agent", "ZeroBahtOS/0.1"), int(config.get("max_items_per_feed", 20)))
            all_items.extend(items)
            successful_feeds += 1
            log_event("research_feed_success", feed=feed, item_count=len(items))
        except Exception as exc:
            log_event("research_feed_failed", feed=feed, error=type(exc).__name__, detail=str(exc)[:250])
    if not all_items:
        all_items = _load_seed_data(int(config.get("max_items_per_feed", 20)))
        if all_items:
            log_event("research_fallback_used", provider="local_seed_data", item_count=len(all_items))
        else:
            log_event("research_fallback_empty", provider="local_seed_data")
    keywords = [str(k).lower() for k in config.get("keywords", [])]
    for item in all_items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        matched = [k for k in keywords if k in text]
        item["score"] = len(matched)
        item["matched_keywords"] = matched
        item["researched_at"] = datetime.now(timezone.utc).isoformat()
    all_items.sort(key=lambda x: (x.get("score", 0), x.get("title", "")), reverse=True)
    out = ROOT / "data" / "research"
    out.mkdir(parents=True, exist_ok=True)
    (out / "opportunities.json").write_text(json.dumps(all_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "keywords.json").write_text(json.dumps({"keywords": config.get("keywords", []), "generated_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return all_items

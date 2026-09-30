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


def _clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


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
            published = _text(item, ["{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
            results.append({
                "title": title,
                "url": link,
                "summary": _clean_text(summary)[:1000],
                "source": url,
                "published": published,
            })
        return results
    results = []
    for item in items[:limit]:
        title = _text(item, ["title"])
        link = _text(item, ["link"])
        summary = _text(item, ["description", "summary", "content:encoded"])
        published = _text(item, ["pubDate", "published", "updated"])
        results.append({
            "title": title,
            "url": link,
            "summary": _clean_text(summary)[:1000],
            "source": url,
            "published": published,
        })
    return results


def _load_seed_data(limit):
    path = ROOT / "data" / "research" / "seed.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data[:limit] if isinstance(data, list) else []
    except Exception as exc:
        log_event("research_seed_failed", error=type(exc).__name__, detail=str(exc)[:250])
        return []


def _normalize(value):
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _score_item(item, keywords):
    text = _normalize((item.get("title", "") + " " + item.get("summary", "")))
    matched = sorted({k for k in keywords if _normalize(k) and _normalize(k) in text}, key=len, reverse=True)
    intent_terms = {
        "how to": 2, "guide": 2, "compare": 2, "review": 2, "price": 2, "problem": 2,
        "วิธี": 2, "รีวิว": 2, "เปรียบเทียบ": 2, "ราคา": 2, "แก้ปัญหา": 2, "คู่มือ": 2
    }
    intent_score = sum(weight for term, weight in intent_terms.items() if term in text)
    keyword_score = sum(min(len(k.split()), 3) for k in matched)
    return matched, keyword_score, intent_score, keyword_score + intent_score


def _dedupe(items):
    seen = set()
    unique = []
    for item in items:
        key = (_normalize(item.get("title")), _normalize(item.get("url")))
        if key == ("", "") or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def run_research(config):
    all_items = []
    for feed in config.get("rss_feeds", []):
        try:
            items = _fetch_feed(feed, config.get("user_agent", "ZeroBahtOS/0.1"), int(config.get("max_items_per_feed", 20)))
            all_items.extend(items)
            log_event("research_feed_success", feed=feed, item_count=len(items))
        except Exception as exc:
            log_event("research_feed_failed", feed=feed, error=type(exc).__name__, detail=str(exc)[:250])

    all_items = _dedupe(all_items)
    if not all_items:
        all_items = _load_seed_data(int(config.get("max_items_per_feed", 20)))
        if all_items:
            log_event("research_fallback_used", provider="local_seed_data", item_count=len(all_items))
        else:
            log_event("research_fallback_empty", provider="local_seed_data")

    keywords = [str(k) for k in config.get("keywords", [])]
    for item in all_items:
        matched, keyword_score, intent_score, total = _score_item(item, keywords)
        item["matched_keywords"] = matched
        item["keyword_score"] = keyword_score
        item["intent_score"] = intent_score
        item["opportunity_score"] = total
        item["research_quality"] = "seed_unverified" if item.get("source") == "local_seed_data" else "public_feed"
        item["researched_at"] = datetime.now(timezone.utc).isoformat()

    all_items.sort(
        key=lambda x: (
            x.get("opportunity_score", 0),
            x.get("intent_score", 0),
            x.get("keyword_score", 0),
            x.get("title", ""),
        ),
        reverse=True,
    )
    out = ROOT / "data" / "research"
    out.mkdir(parents=True, exist_ok=True)
    (out / "opportunities.json").write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "keywords.json").write_text(
        json.dumps(
            {
                "keywords": config.get("keywords", []),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "scoring": "keyword_score + intent_score",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    log_event(
        "research_ranked",
        candidate_count=len(all_items),
        selected_count=min(len(all_items), int(config.get("max_drafts_per_run", 5))),
    )
    return all_items

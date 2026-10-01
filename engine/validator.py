import json
from urllib.parse import urlparse
from pathlib import Path
from .logger import log_event

ROOT = Path(__file__).resolve().parents[1]

def validate_drafts(paths):
    results = []
    for relative in paths:
        path = ROOT / relative
        errors = []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            source_url = data.get("source_url", "")
            if not source_url:
                errors.append("missing_source_url")
            else:
                parsed = urlparse(source_url.strip())
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    errors.append("invalid_source_url")
            if data.get("status") != "draft_requires_human_review":
                errors.append("unexpected_status")
            if data.get("first_hand_experience_claimed"):
                errors.append("unsupported_experience_claim")
            formats = data.get("formats", {})
            if not formats.get("affiliate_disclosure"):
                errors.append("missing_affiliate_disclosure")
            if not formats.get("seo_article_outline", {}).get("sections"):
                errors.append("missing_article_outline")
            if not data.get("source_feed"):
                errors.append("missing_source_feed")
            if data.get("research_quality") in {"seed_unverified", "stale_unverified", "unknown"}:
                errors.append("unverified_research")
            if data.get("freshness") != "fresh":
                errors.append("unverified_freshness")
            if not data.get("source_title"):
                errors.append("missing_source_title")
        except Exception as exc:
            errors.append("invalid_json:" + type(exc).__name__)
        result = {"path": relative, "passed": not errors, "errors": errors}
        results.append(result)
        log_event("draft_validation", **result)
    out = ROOT / "data" / "analytics"
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results

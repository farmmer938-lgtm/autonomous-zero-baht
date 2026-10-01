import json
import re
from datetime import datetime, timezone
from pathlib import Path
from .logger import log_event

ROOT = Path(__file__).resolve().parents[1]

def _slug(text):
    slug = re.sub(r"[^a-zA-Z0-9ก-๙]+", "-", text.lower()).strip("-")
    return slug[:80] or "untitled"

def create_draft(item):
    title = (item.get("title") or "หัวข้อที่น่าสนใจ").strip()
    url = item.get("url", "")
    summary = (item.get("summary") or "").strip()
    source = item.get("source", "")
    disclosure = "Disclosure: หากมีลิงก์ Affiliate ในฉบับเผยแพร่ ผู้จัดทำอาจได้รับค่าคอมมิชชันโดยไม่มีค่าใช้จ่ายเพิ่มสำหรับผู้ซื้อ"
    return {
        "id": _slug(title),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_title": title,
        "source_url": url,
        "source_feed": source,
        "research_quality": item.get("research_quality", "unknown"),
        "freshness": item.get("freshness", "unknown"),
        "research_score": item.get("opportunity_score", 0),
        "formats": {
            "seo_article_outline": {
                "title": title,
                "sections": [
                    "ปัญหาหรือคำถามที่ผู้อ่านต้องการคำตอบ",
                    "ข้อมูลพื้นฐานและข้อเท็จจริงที่ตรวจสอบได้",
                    "ทางเลือกหรือขั้นตอนที่ผู้อ่านนำไปใช้ได้",
                    "ข้อจำกัดและสิ่งที่ควรตรวจสอบเพิ่มเติม",
                    "สรุปและขั้นตอนถัดไป"
                ],
                "source_summary_for_editor": summary,
                "source_url": url
            },
            "facebook_post": f"กำลังรวบรวมข้อมูลเรื่อง: {title}\n\nก่อนตัดสินใจ ควรตรวจสอบแหล่งข้อมูลและเปรียบเทียบทางเลือกให้เหมาะกับความต้องการของตนเอง\n\nแหล่งข้อมูลสำหรับตรวจสอบ: {url}",
            "short_video_script": f"Hook: คุณกำลังหาข้อมูลเรื่อง {title} อยู่หรือไม่?\n\nเนื้อหา: เริ่มจากตรวจสอบข้อมูลต้นทาง เปรียบเทียบข้อเท็จจริงและข้อจำกัด อย่าตัดสินใจจากพาดหัวเพียงอย่างเดียว\n\nCTA: อ่านข้อมูลต้นทางและตรวจสอบรายละเอียดเพิ่มเติมได้ที่ {url}",
            "affiliate_disclosure": disclosure
        },
        "status": "draft_requires_human_review",
        "first_hand_experience_claimed": False
    }

def generate_drafts(items, limit=5, output_dir=None):
    if limit <= 0:
        return []
    out = Path(output_dir) if output_dir else ROOT / "data" / "content" / "drafts"
    out.mkdir(parents=True, exist_ok=True)
    created = []
    seen = set()
    used_ids = set()
    for item in items:
        if item.get("freshness") != "fresh" or item.get("research_quality") != "public_feed":
            continue
        title = (item.get("title") or "").strip()
        normalized_title = re.sub(r"\s+", " ", title).casefold()
        if not title or normalized_title in seen:
            continue
        seen.add(normalized_title)
        draft = create_draft(item)
        base_id = draft["id"]
        draft_id = base_id
        suffix = 2
        while draft_id in used_ids:
            draft_id = f"{base_id}-{suffix}"
            suffix += 1
        used_ids.add(draft_id)
        draft["id"] = draft_id
        path = out / f"{draft_id}.json"
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path))
        log_event("draft_created", draft_id=draft["id"], path=created[-1])
        if len(created) >= limit:
            break
    return created

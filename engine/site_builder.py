"""Render validated drafts into a public static site (GitHub Pages).

This is the distribution stage: it turns internal repository artifacts into
pages a real audience can read. It is zero-cost (static files only), makes no
network calls, and never invents traffic, engagement, or revenue.
"""
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .logger import log_event

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "site"
POSTS_DIR = SITE_DIR / "p"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9ก-๙]+", "-", (value or "").lower()).strip("-")
    return slug[:70] or "post"


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _load_drafts(draft_paths):
    drafts = []
    for relative in draft_paths:
        path = ROOT / relative
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("status") != "draft_requires_human_review":
            continue
        drafts.append(data)
    return drafts


def _page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<style>
:root{{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Thai",sans-serif}}
.wrap{{max-width:820px;margin:0 auto;padding:28px 18px 72px}}
h1{{font-size:26px;margin:0 0 6px}}
h2{{font-size:19px;margin:28px 0 10px;border-left:3px solid var(--acc);padding-left:10px}}
a{{color:var(--acc)}}
.card{{background:var(--card);border:1px solid #21262d;border-radius:12px;padding:14px 16px;margin:12px 0}}
.mut{{color:var(--mut);font-size:14px}}
ul{{padding-left:20px}}
.foot{{margin-top:34px;border-top:1px solid #21262d;padding-top:14px}}
</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>
"""


def build_site(draft_paths):
    drafts = _load_drafts(draft_paths)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    index = []

    for data in drafts:
        pid = _slug(data.get("id") or data.get("source_title") or "post")
        title = data.get("source_title") or pid
        source_url = data.get("source_url", "")
        outline = data.get("formats", {}).get("seo_article_outline", {})
        sections = outline.get("sections", [])
        summary = outline.get("source_summary_for_editor", "")
        disclosure = data.get("formats", {}).get("affiliate_disclosure", "")

        body = [f"<h1>{_esc(title)}</h1>",
                f'<p class="mut">ตรวจสอบข้อมูลต้นทาง: <a href="{_esc(source_url)}" rel="noopener nofollow">{_esc(source_url)}</a></p>',
                "<h2>สรุป</h2>", f"<div class='card'>{_esc(summary)}</div>",
                "<h2>ประเด็นที่ควรตรวจสอบ</h2>", "<ul>" + "".join(f"<li>{_esc(s)}</li>" for s in sections) + "</ul>",
                "<h2>ข้อจำกัด</h2>",
                "<p class='mut'>หน้านี้สรุปและชี้แหล่งข้อมูลต้นทาง ไม่ได้ยืนยันข้อเท็จจริงแทนผู้อ่าน "
                "โปรดตรวจสอบกับแหล่งต้นทางก่อนตัดสินใจ</p>",
                f"<div class='foot mut'>{_esc(disclosure)}<br>เผยแพร่อัตโนมัติโดย Autonomous Zero-Baht Business OS · {_esc(now)}</div>"]
        (POSTS_DIR / f"{pid}.html").write_text(_page_shell(title, "".join(body)), encoding="utf-8")
        index.append({"id": pid, "title": title, "source_url": source_url,
                      "score": data.get("research_score", 0)})

    cards = "".join(
        f'<div class="card"><a href="p/{_esc(item["id"])}.html"><strong>{_esc(item["title"])}</strong></a>'
        f'<div class="mut">คะแนนโอกาส: {_esc(item["score"])} · ต้นทาง: {_esc(item["source_url"])}</div></div>'
        for item in index
    )
    home = [f"<h1>Zero-Baht Research</h1>",
            f'<p class="mut">สรุปข่าวเทคโนโลยีและเรื่องที่ควรตรวจสอบ · อัปเดตอัตโนมัติ · {_esc(now)}</p>',
            f'<p class="mut">ทั้งหมด {len(index)} เรื่อง</p>', cards or "<p>ยังไม่มีเนื้อหา</p>",
            "<div class='foot mut'>ระบบวิจัย-ร่าง-ตรวจ-เผยแพร่ อัตโนมัติ ต้นทุน ฿0 · "
            "ไม่มีการกล่าวอ้างรายได้หรือยอดผู้เข้าชมที่ยังไม่ได้รับการยืนยันจากแหล่งภายนอก</div>"]
    (SITE_DIR / "index.html").write_text(_page_shell("Zero-Baht Research", "".join(home)), encoding="utf-8")

    (SITE_DIR / "index.json").write_text(
        json.dumps({"generated_at": now, "count": len(index), "items": index},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    record = {"timestamp": now, "pages_built": len(index), "provider": "github_pages",
              "public_url": "https://farmmer938-lgtm.github.io/autonomous-zero-baht/",
              "external_distribution": "built_static_site_pending_deploy"}
    log_event("site_built", **record)
    return record

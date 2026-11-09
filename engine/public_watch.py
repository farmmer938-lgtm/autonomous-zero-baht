"""Public-surface watchdog (GitHub Actions, free, no secrets).

Runs on GitHub's infrastructure instead of a quota-limited OpenHands sandbox, so it can
check AF's public revenue surfaces every few minutes at zero cost and zero token use.
Everything it reads is public: no credentials, so nothing sensitive can leak.

It writes data/public_watch.json and exits non-zero if a critical surface is down, which
makes GitHub email the owner automatically.

Entrypoint: python -m engine.public_watch
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public_watch.json"

SURFACES = {
    "storefront": ("https://app.do.ink/stores/navintas", "critical"),
    "catalog": ("https://farmmer938-lgtm.github.io/aeris-store/af-studio-m938-2/", "critical"),
    "research_site": ("https://farmmer938-lgtm.github.io/autonomous-zero-baht/", "critical"),
    # AF's x402 cashier runs inside the OpenHands sandbox, so its public host embeds the
    # container RUNTIME_ID and changes on every restart. The live URL is resolved at run
    # time from data/live_endpoint.json (published at each bring-up by AF), never hardcoded,
    # so this check follows the cashier instead of probing a stale host. Informational only.
    "cashier": (CASHIER_FALLBACK, "info"),
    # Third-party rail: AF cannot repair it, so an outage is informational only.
    "opentask": ("https://opentask.ai/api/tasks", "info"),
}

# The cashier URL is ephemeral (host embeds the container RUNTIME_ID). Resolve it from the
# live endpoint AF publishes on each bring-up; fall back to the last known host only if the
# manifest is unreadable, so a transient fetch error never turns into a false outage.
LIVE_ENDPOINT = ("https://raw.githubusercontent.com/farmmer938-lgtm/"
                 "autonomous-zero-baht/main/data/live_endpoint.json")
CASHIER_FALLBACK = "https://work-1-mbagwhmoyaqtbyvu.prod-runtime.all-hands.dev/openapi.json"

UA = {"User-Agent": "af-public-watch/1.0"}

# A critical surface that blips across sandbox restarts only emails the owner after this
# many consecutive failed checks, so one 10-minute blip is never an email.
SUSTAINED_DOWN = 3


def fetch(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def cashier_url() -> str:
    """Resolve the cashier's current public discovery URL from AF's published manifest."""
    code, body = fetch(LIVE_ENDPOINT, timeout=15)
    if code == 200:
        try:
            url = (json.loads(body).get("cashier") or {}).get("openapi")
            if url:
                return url
        except Exception:
            pass
    return CASHIER_FALLBACK


def funded_titles(body: str):
    try:
        data = json.loads(body)
    except Exception:
        return []
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    out = []
    for t in tasks:
        b = t.get("budgetText") or ""
        if b and b not in ("0 USDC", "Unpaid pilot — public credit only",
                           "Free - community contribution") and "internal" not in b:
            out.append(t.get("title"))
    return sorted(x for x in out if x)


def radar_items():
    """Open, claimable paid work across the public rails. All endpoints are public."""
    items = []

    code, body = fetch("https://gofrantic.com/v1/board")
    if code == 200:
        try:
            rows = json.loads(body)
            rows = rows.get("board") or rows.get("bounties") or []
            if isinstance(rows, dict):
                rows = rows.get("bounties", [])
            for b in rows:
                if b.get("work_status") != "open":
                    continue
                n = b.get("number")
                items.append({
                    "rail": "frantic",
                    "id": f"frantic:{n}",
                    "title": (b.get("title") or "")[:100],
                    "reward_usd": b.get("price_usd") or 0,
                    "visibility": b.get("visibility"),
                    "url": f"https://gofrantic.com/bounties/{n}",
                })
        except Exception:
            pass

    code, body = fetch("https://api.nonsynthetic.net/api/v1/board/tasks?status=open")
    if code == 200:
        try:
            for t in json.loads(body).get("tasks", []):
                items.append({
                    "rail": "nonsynthetic",
                    "id": f"ns:{t.get('id')}",
                    "title": (t.get("title") or "")[:100],
                    "reward_usd": t.get("reward_usd") or 0,
                    "visibility": "public",
                    "url": "https://nonsynthetic.net/",
                })
        except Exception:
            pass

    return items


def render_dashboard(report):
    """Self-contained status page (no JS, no external assets) for K to bookmark."""
    s = report["surfaces"]

    def row(name, label):
        e = s.get(name, {})
        ok = e.get("ok")
        tier = e.get("tier")
        badge = "UP" if ok else ("DOWN" if tier == "critical" else "OFFLINE")
        color = "#0a7d33" if ok else ("#b00020" if tier == "critical" else "#8a6d00")
        extra = ""
        if name == "opentask":
            extra = f" &middot; {e.get('funded_tasks', '?')} funded tasks"
        note = "" if tier == "critical" else " <span style=\"color:#888;font-size:12px\">(informational)</span>"
        return (f"<tr><td>{label}{note}</td>"
                f"<td><span style=\"color:{color};font-weight:700\">{badge}</span>"
                f" &middot; HTTP {e.get('http')}{extra}</td>"
                f"<td><a href=\"{e.get('url')}\">open</a></td></tr>")

    tasks = s.get("opentask", {}).get("funded_titles", []) or []
    items = "".join(f"<li>{t}</li>" for t in tasks[:15]) or "<li>(none)</li>"
    radar = report.get("radar", []) or []
    if radar:
        radar_html = "".join(
            f"<li><b>${r.get('reward_usd')}</b> &middot; {r.get('rail')} &middot; "
            f"<a href=\"{r.get('url')}\">{r.get('title')}</a></li>"
            for r in sorted(radar, key=lambda x: -(x.get("reward_usd") or 0))[:20])
    else:
        radar_html = "<li>(none open)</li>"
    head_color = "#0a7d33" if report["healthy"] else "#b00020"
    head_text = "ALL SYSTEMS UP" if report["healthy"] else f"DOWN: {', '.join(report['down'])}"
    return f"""<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AF Status</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f7f9;color:#1a1a1a}}
 .wrap{{max-width:760px;margin:0 auto;padding:24px}}
 h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#666;font-size:13px;margin-bottom:18px}}
 .head{{background:{head_color};color:#fff;padding:14px 18px;border-radius:10px;font-weight:700;margin-bottom:18px}}
 table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden}}
 td,th{{padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;text-align:left}}
 th{{background:#fafafa;color:#555;font-weight:600}}
 ul{{background:#fff;border-radius:10px;padding:14px 30px;font-size:14px;line-height:1.6}}
 code{{background:#eee;padding:2px 6px;border-radius:4px;font-size:12px}}
</style></head><body><div class="wrap">
<h1>AF Status</h1>
<div class="sub">ตรวจอัตโนมัติทุก 10 นาที โดย GitHub Actions (ฟรี, ไม่ใช้โควตา) &middot; อัปเดตล่าสุด {report['checked_at']}</div>
<div class="head">{head_text}</div>
<table><tr><th>Surface</th><th>State</th><th></th></tr>
{row('storefront', 'Do.ink storefront')}
{row('catalog', 'Public catalog')}
{row('research_site', 'Research site')}
{row('cashier', 'x402 cashier (AF DataBridge)')}
{row('opentask', 'OpenTask (funded work)')}
</table>
<h1 style="margin-top:24px">งานมีเงินบน OpenTask</h1>
<ul>{items}</ul>
<h1 style="margin-top:24px">Opportunity radar — งานเปิดใหม่ (Frantic + nonsynthetic)</h1>
<ul>{radar_html}</ul>
<p class="sub">source: <code>engine/public_watch.py</code></p>
</div></body></html>
"""


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()

    prev = None
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            prev = None
    prev_surfaces = (prev or {}).get("surfaces", {})

    surfaces_cfg = dict(SURFACES)
    surfaces_cfg["cashier"] = (cashier_url(), "info")
    surfaces, down = {}, []
    for name, (url, tier) in surfaces_cfg.items():
        code, body = fetch(url)
        ok = code == 200
        entry = {"url": url, "http": code, "ok": ok, "tier": tier}
        if name == "opentask":
            titles = funded_titles(body)
            entry["funded_tasks"] = len(titles)
            entry["funded_titles"] = titles
        prev_down = int(prev_surfaces.get(name, {}).get("consecutive_down", 0) or 0)
        entry["consecutive_down"] = 0 if ok else prev_down + 1
        surfaces[name] = entry
        # Only a critical surface that stays down for several checks emails the owner.
        # Informational surfaces (the ephemeral sandbox cashier, third-party rails) never do.
        if not ok and tier == "critical" and entry["consecutive_down"] >= SUSTAINED_DOWN:
            down.append(name)

    report = {"schema": "af.public_watch.v1", "checked_at": now,
              "healthy": not down, "down": down, "surfaces": surfaces,
              "radar": radar_items()}
    seen = {i["id"] for i in (prev or {}).get("radar", [])}
    report["new_items"] = [i for i in report["radar"] if i["id"] not in seen]
    changed = not prev or prev.get("down") != down or [
        s.get("ok") for s in (prev or {}).get("surfaces", {}).values()
    ] != [s.get("ok") for s in surfaces.values()]
    if prev and prev.get("surfaces", {}).get("opentask", {}).get("funded_titles") != \
            surfaces["opentask"].get("funded_titles"):
        changed = True
    if report["new_items"]:
        changed = True
    report["changed"] = bool(changed)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    status_page = ROOT / "site" / "status.html"
    status_page.parent.mkdir(parents=True, exist_ok=True)
    status_page.write_text(render_dashboard(report), encoding="utf-8")
    print(json.dumps({"healthy": report["healthy"], "down": down,
                      "opentask_funded": surfaces["opentask"].get("funded_tasks")},
                     ensure_ascii=False))
    if down:
        print(f"ALERT: surfaces down -> {down}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

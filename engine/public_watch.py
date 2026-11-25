"""Public-surface watchdog (GitHub Actions, free, no secrets).

Runs on GitHub's infrastructure instead of a quota-limited OpenHands sandbox, so it can
check AF's public revenue surfaces at zero cost and zero token use. Everything it reads is
public: no credentials, so nothing sensitive can leak.

It writes data/public_watch.json and site/status.html. The workflow keeps the job green on
purpose (K is not in the loop) and reports problems through the "af-alert" issue instead of
an email, so this tool's exit code is a signal for that issue, not for GitHub's mailer.

Entrypoint: python -m engine.public_watch
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public_watch.json"

# The cashier URL is ephemeral (host embeds the container RUNTIME_ID). Resolve it from the
# live endpoint AF publishes on each bring-up; fall back to the last known host only if the
# manifest is unreadable, so a transient fetch error never turns into a false outage.
LIVE_ENDPOINT = ("https://raw.githubusercontent.com/farmmer938-lgtm/"
                 "autonomous-zero-baht/main/data/live_endpoint.json")
CASHIER_FALLBACK = "https://work-1-mbagwhmoyaqtbyvu.prod-runtime.all-hands.dev/openapi.json"

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

UA = {"User-Agent": "af-public-watch/1.0"}

# The published order index is the machine-readable promise that a buyer gets something back,
# so it is checked separately from the pages that merely render it.
ORDERS_INDEX = ("https://farmmer938-lgtm.github.io/autonomous-zero-baht/"
                "api/orders/index.json")
ORDERS_MAX_AGE_H = 24

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


def orders_state(index, now=None, max_age_h=ORDERS_MAX_AGE_H):
    """(state, note) for the published order index. state is ok / warn / fail.

    A stale index is a warning, not a failure: the file still answers and still tells the
    truth, it just has not been rebuilt. A wrong schema or a missing pay_to is a failure,
    because a buyer cannot pay the right address from it.
    """
    if not isinstance(index, dict):
        return "fail", "order index is not a JSON object"
    if index.get("schema") != "af.api.orders.v1":
        return "fail", f"unexpected schema {index.get('schema')!r}"
    pay_to = str(index.get("pay_to") or "")
    if not (pay_to.startswith("0x") and len(pay_to) == 42):
        return "fail", "pay_to is not an address"
    stamp = str(index.get("generatedAt") or "")
    try:
        generated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return "warn", f"generatedAt is not a timestamp: {stamp!r}"
    age_h = ((now or datetime.now(timezone.utc)) - generated).total_seconds() / 3600
    if age_h > max_age_h:
        return "warn", f"order index is {age_h:.1f}h old"
    return "ok", f"{len(index.get('orders') or [])} order(s), {age_h:.1f}h old"


def payment_target_state(orders, verify):
    """(state, note): the address buyers pay must be the address revenue is counted from."""
    pay_to = str((orders or {}).get("pay_to") or "").lower()
    wallet = str((verify or {}).get("wallet") or "").lower()
    if not pay_to or not wallet:
        return "warn", "cannot compare pay_to with the revenue wallet"
    if pay_to != wallet:
        return "fail", f"buyers pay {pay_to} but revenue is read from {wallet}"
    return "ok", "orders and revenue read the same wallet"


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


def canonical_url(url):
    """A comparable URL, or None when it points at a site root and so identifies no job.

    All 200 nonsynthetic listings share `https://nonsynthetic.net/`; using that as a dedup
    key would collapse 200 different jobs into one, so a bare origin is not an identity.
    """
    raw = str(url or "").strip().lower()
    if not raw:
        return None
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^www\.", "", raw)
    raw = raw.split("#")[0].rstrip("/")
    if "/" not in raw:
        return None
    return raw


def fingerprint(title):
    """Stable identity for a job reposted under a new id: '… [v72]' and '… [v73]' match."""
    text = str(title or "").lower()
    text = re.sub(r"\[v\d+\]", " ", text)
    text = re.sub(r"[^a-z0-9ก-๙]+", " ", text).strip()
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def dedupe(items):
    """One row per piece of work, keeping the most valuable and most recent copy."""
    def rank(item):
        return (1 if item.get("funded") else 0,
                1 if item.get("claimable") else 0,
                float(item.get("reward_usd") or 0),
                str(item.get("posted_at") or ""))

    kept, index = [], {}
    for item in sorted(items, key=rank, reverse=True):
        keys = [("id", item.get("id")), ("fp", fingerprint(item.get("title")))]
        url = canonical_url(item.get("url"))
        if url:
            keys.append(("url", url))
        if any(k in index for k in keys):
            first = next(index[k] for k in keys if k in index)
            first["duplicates"] = first.get("duplicates", 0) + 1
            continue
        for k in keys:
            index[k] = item
        kept.append(item)
    return kept


def radar_items(now=None):
    """Open, claimable work across the public rails, deduplicated and attributed.

    Every row carries the endpoint it came from and when it was read, plus whether the
    money is actually held by the rail (`funded`) instead of merely advertised.
    """
    checked = now or datetime.now(timezone.utc).isoformat()
    items = []

    source = "https://gofrantic.com/v1/board"
    code, body = fetch(source)
    if code == 200:
        try:
            rows = json.loads(body)
            rows = rows.get("board") or rows.get("bounties") or []
            if isinstance(rows, dict):
                rows = rows.get("open_bounties") or rows.get("bounties") or []
            for b in rows:
                if b.get("work_status") != "open":
                    continue
                slots = b.get("claim_slots") or {}
                actions = b.get("actions") or {}
                claim = actions.get("claim") or {}
                available = slots.get("available")
                items.append({
                    "rail": "frantic",
                    "id": f"frantic:{b.get('number')}",
                    "title": (b.get("title") or "")[:100],
                    "reward_usd": b.get("price_usd") or 0,
                    "visibility": b.get("visibility"),
                    "url": "https://gofrantic.com" + str(b.get("url") or f"/bounties/{b.get('number')}"),
                    "source_url": source,
                    "verified_at": checked,
                    "posted_at": b.get("posted_at"),
                    "funded": bool(b.get("funded")),
                    "claimable": bool(claim.get("available")) and (available is None or available > 0),
                    "claim_state": claim.get("state"),
                    "expires_at": None,
                    "reward_basis": "escrow" if b.get("funded") else "advertised",
                })
        except Exception:
            pass

    source = "https://api.nonsynthetic.net/api/v1/board/tasks?status=open"
    code, body = fetch(source)
    if code == 200:
        try:
            for t in json.loads(body).get("tasks", []):
                if str(t.get("state") or "open").lower() != "open":
                    continue
                reward = t.get("effective_reward_usd")
                if reward in (None, ""):
                    reward = t.get("reward_usd") or 0
                items.append({
                    "rail": "nonsynthetic",
                    "id": f"ns:{t.get('id')}",
                    "title": (t.get("title") or "")[:100],
                    "reward_usd": reward or 0,
                    "visibility": "public",
                    "url": "https://nonsynthetic.net/",
                    "source_url": source,
                    "verified_at": checked,
                    "posted_at": t.get("created_ts"),
                    # `house_funded` is the rail paying its own credits, not escrow: on
                    # 2026-11-25 all 200 open tasks had pool_funded=false and
                    # reward_asset="cr", so only pool money counts as held.
                    "funded": bool(t.get("pool_funded")),
                    "claimable": bool(t.get("claim_here")) and bool(t.get("open_to_all")),
                    "claim_state": t.get("state"),
                    "expires_at": t.get("claim_expires_at") or t.get("auto_release_at"),
                    "reward_asset": t.get("reward_asset"),
                    "reward_basis": ("escrow" if t.get("pool_funded")
                                     else "credit estimate" if t.get("house_funded")
                                     else "advertised"),
                })
        except Exception:
            pass

    return dedupe(items)


def paid_only(items):
    """Only a listing that states a reward may be called paid work in an alert."""
    out = []
    for i in items:
        try:
            if float(i.get("reward_usd") or 0) > 0:
                out.append(i)
        except (TypeError, ValueError):
            continue
    return out


def funded_only(items):
    """Advertised money is not held money: keep only rows the rail says it holds."""
    return [i for i in items if i.get("funded")]


def _reward(item) -> str:
    """`$0` claims a value; a listing that states no USD price is unpriced, not worthless."""
    try:
        usd = float(item.get("reward_usd") or 0)
    except (TypeError, ValueError):
        return "unpriced"
    return f"${usd:g}" if usd > 0 else "unpriced"


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _safe_url(value) -> str:
    """Only http(s) links may reach an href; anything else becomes '#'."""
    url = str(value or "").strip()
    return _esc(url) if url.lower().startswith(("http://", "https://")) else "#"


def render_dashboard(report):
    """Self-contained status page (no JS, no external assets) for K to bookmark.

    Every value below comes from a third-party API, so all of it is escaped: a bounty
    title is attacker-controlled text and must never become markup on a public page.
    """
    s = report["surfaces"]

    def row(name, label):
        e = s.get(name, {})
        ok = e.get("ok")
        tier = e.get("tier")
        state = e.get("state")
        badge = ("WARN" if state == "warn"
                 else "UP" if ok else ("FAIL" if tier == "critical" else "OFFLINE"))
        color = "#0a7d33" if ok else ("#b00020" if tier == "critical" else "#8a6d00")
        extra = ""
        if name == "opentask":
            extra = " &middot; %s funded tasks" % _esc(e.get("funded_tasks", "?"))
        note = "" if tier == "critical" else " <span style=\"color:#888;font-size:12px\">(informational)</span>"
        if e.get("note"):
            extra += " &middot; <span style=\"color:#777;font-size:12px\">{}</span>".format(_esc(e["note"]))
        return (f"<tr><td>{label}{note}</td>"
                f"<td><span style=\"color:{color};font-weight:700\">{badge}</span>"
                f" &middot; HTTP {_esc(e.get('http'))}{extra}</td>"
                f"<td><a href=\"{_safe_url(e.get('url'))}\" rel=\"noopener nofollow\">open</a></td></tr>")

    tasks = s.get("opentask", {}).get("funded_titles", []) or []
    items = "".join(f"<li>{_esc(t)}</li>" for t in tasks[:15]) or "<li>(none)</li>"
    radar = report.get("radar", []) or []
    if radar:
        def badge(item):
            marks = []
            marks.append("funded" if item.get("funded") else "advertised only")
            if item.get("claimable") is False:
                marks.append("not claimable")
            if item.get("duplicates"):
                marks.append(f"{item['duplicates']} duplicate(s) merged")
            return " &middot; ".join(marks)

        radar_html = "".join(
            f"<li><b>{_esc(_reward(r))}</b> &middot; {_esc(r.get('rail'))} &middot; "
            f"<a href=\"{_safe_url(r.get('url'))}\" rel=\"noopener nofollow\">{_esc(r.get('title'))}</a>"
            f"<br><span style=\"color:#777;font-size:12px\">{_esc(badge(r))}</span></li>"
            for r in sorted(radar, key=lambda x: (not x.get("funded"), -(float(x.get("reward_usd") or 0))))[:20])
    else:
        radar_html = "<li>(none open)</li>"
    degraded = report.get("degraded", []) or []
    if report["down"]:
        head_color, head_text = "#b00020", "DOWN: " + ", ".join(report["down"])
    elif degraded:
        head_color = "#8a6d00"
        head_text = "DEGRADED: %s offline (informational)" % ", ".join(degraded)
    else:
        head_color, head_text = "#0a7d33", "ALL SYSTEMS UP"
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
<div class="sub">ตรวจด้วย GitHub Actions ตามตาราง cron ของ workflow (GitHub เป็นผู้กำหนดความถี่จริง)
&middot; รอบตรวจล่าสุด {_esc(report['checked_at'])}</div>
<div class="head">{head_text}</div>
<table><tr><th>Surface</th><th>State</th><th></th></tr>
{row('storefront', 'Do.ink storefront')}
{row('catalog', 'Public catalog')}
{row('research_site', 'Research site')}
{row('cashier', 'x402 cashier (AF DataBridge)')}
{row('opentask', 'OpenTask (funded work)')}
{row('orders_index', 'Published order index')}
{row('payment_target', 'Payment target vs revenue wallet')}
</table>
<h1 style="margin-top:24px">งานมีเงินบน OpenTask</h1>
<ul>{items}</ul>
<h1 style="margin-top:24px">Opportunity radar — งานเปิดใหม่ (Frantic + nonsynthetic)</h1>
<p class="sub">รายการเหล่านี้เป็นประกาศจากบุคคลที่สาม AF ยังไม่ได้ตรวจสอบว่าจ่ายจริง
&middot; ตัวเลข $ คือรางวัลที่ประกาศไว้ ไม่ใช่รายได้ของ AF
&middot; &quot;unpriced&quot; = ประกาศไม่ได้ระบุเป็นดอลลาร์ (เช่น RTC/MRG) ไม่ได้แปลว่าไม่มีค่า</p>
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

    # An informational surface being down is still a fact worth publishing: the cashier is
    # where money is meant to arrive, so a green "ALL SYSTEMS UP" would be a false claim.
    # The order index and the payment target are checked on their own, so a dead cashier
    # cannot hide a broken order file (and the other way round).
    code, body = fetch(ORDERS_INDEX)
    try:
        index = json.loads(body) if code == 200 else None
    except Exception:
        index = None
    state, note = (orders_state(index) if index is not None
                   else ("fail", f"order index answered HTTP {code}"))
    surfaces["orders_index"] = {"url": ORDERS_INDEX, "http": code, "ok": state != "fail",
                                "tier": "critical", "state": state, "note": note,
                                "consecutive_down": 0 if state != "fail" else
                                int(prev_surfaces.get("orders_index", {}).get("consecutive_down", 0) or 0) + 1}
    try:
        verify = json.loads((ROOT / "data" / "revenue_verify.json").read_text(encoding="utf-8"))
    except Exception:
        verify = {}
    state, note = payment_target_state(index, verify)
    surfaces["payment_target"] = {"url": ORDERS_INDEX, "http": code, "ok": state != "fail",
                                  "tier": "critical", "state": state, "note": note,
                                  "consecutive_down": 0}
    for name in ("orders_index", "payment_target"):
        if surfaces[name]["state"] == "fail":
            surfaces[name]["ok"] = False

    degraded = [name for name, e in surfaces.items() if not e["ok"] and e["tier"] != "critical"]
    # FAIL means someone must act now; WARN means look later. They are never merged.
    fail = sorted({n for n, e in surfaces.items() if e.get("state") == "fail"}
                  | {n for n in down})
    warn = sorted({n for n, e in surfaces.items() if e.get("state") == "warn"}
                  | set(degraded))
    report = {"schema": "af.public_watch.v1", "checked_at": now,
              "healthy": not fail, "fail": fail, "warn": warn,
              "down": down, "degraded": degraded, "surfaces": surfaces,
              "radar": radar_items()}
    seen = {i["id"] for i in (prev or {}).get("radar", [])}
    report["new_items"] = [i for i in report["radar"] if i["id"] not in seen]
    # An alert about money must name money the rail already holds, otherwise a $0 listing
    # reads as a $10 opportunity and the alert trains K to ignore it.
    report["new_paid_items"] = funded_only(paid_only(report["new_items"]))
    changed = not prev or prev.get("down") != down or prev.get("degraded") != degraded or [
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
    print(json.dumps({"healthy": report["healthy"], "down": down, "degraded": degraded,
                      "opentask_funded": surfaces["opentask"].get("funded_tasks"),
                      "new_paid_items": len(report["new_paid_items"])},
                     ensure_ascii=False))
    if down:
        print(f"ALERT: surfaces down -> {down}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

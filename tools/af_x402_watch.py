#!/usr/bin/env python3
"""Probe AF's public x402 endpoint and publish an honest health record.

K rule (2026-11-26): never list an endpoint anywhere until it has answered for 14 straight
days, so this file exists to measure exactly that — uptime, latency p50/p95, last good answer.

Reads the endpoint from site/data/x402_endpoint.json, appends one sample per run to
site/data/x402_health.json, and never invents a number: a failed probe is recorded as failed.

Run: python3 tools/af_x402_watch.py
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENDPOINT_FILE = Path("site/data/x402_endpoint.json")
HEALTH_FILE = Path("site/data/x402_health.json")
MAX_SAMPLES = 672  # 14 days at 30-minute probes

# Window B needs its own survival proof: if the host dies mid-window, external_hits=0 means "infra
# dead", not "discovery problem". Two consecutive failed probes (~60 min) or a 90-minute gap
# invalidates the window, and the window must be restarted rather than reinterpreted.
WINDOW_A = ("2026-11-26", "2026-12-10")
WINDOW_B = ("2026-12-11", "2026-12-25")
INVALIDATE_CONSECUTIVE_FAILURES = 2
INVALIDATE_MAX_GAP_MIN = 90
CHEAPEST = "/csv_to_json"


def _req(url: str, method: str = "GET", body: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("x-af-self", "1")
    req.add_header("user-agent", "af-probe/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(), int((time.time() - started) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), int((time.time() - started) * 1000)
    except Exception as e:  # noqa: BLE001 - a dead endpoint is data, not a crash
        return 0, str(e).encode()[:200], int((time.time() - started) * 1000)


def probe(base: str) -> dict:
    checks, latency = {}, None
    st, raw, ms = _req(base + "/status")
    checks["status_200"] = st == 200
    status_snapshot = None
    if st == 200:
        latency = ms
        try:
            status_snapshot = json.loads(raw)
            checks["status_json"] = bool(status_snapshot.get("products"))
        except Exception:
            checks["status_json"] = False
    st, _, _ = _req(base + "/health")
    checks["health_200"] = st == 200
    st, raw, _ = _req(base + CHEAPEST, method="POST", body=b"a,b\n1,2", headers={"content-type": "text/csv"})
    payable = False
    if st == 402:
        try:
            accepts = json.loads(raw).get("accepts") or []
            payable = bool(accepts and accepts[0].get("maxAmountRequired"))
        except Exception:
            payable = False
    checks["paywall_402"] = payable
    return {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ok": all(checks.values()), "latency_ms": latency, "checks": checks,
            "status": status_snapshot}


def summarise(samples: list[dict]) -> dict:
    if not samples:
        return {}
    lat = [s["latency_ms"] for s in samples if s.get("latency_ms")]
    last_ok = next((s["at"] for s in reversed(samples) if s.get("ok")), None)
    # a run of consecutive ok samples ending at the newest one
    streak = 0
    for s in reversed(samples):
        if s.get("ok"):
            streak += 1
        else:
            break
    first = datetime.strptime(samples[0]["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return {
        "samples": len(samples),
        "window_start": samples[0]["at"],
        "window_days": round((datetime.now(timezone.utc) - first).total_seconds() / 86400, 2),
        "uptime_pct": round(100 * sum(1 for s in samples if s.get("ok")) / len(samples), 2),
        "current_streak_samples": streak,
        "current_streak_hours": round(streak * 0.5, 1),
        "last_ok_at": last_ok,
        "last_check_at": samples[-1]["at"],
        "last_check_ok": samples[-1].get("ok"),
        "latency_p50_ms": int(statistics.median(lat)) if lat else None,
        "latency_p95_ms": (sorted(lat)[max(0, int(len(lat) * 0.95) - 1)] if lat else None),
        "listable": (len(samples) >= MAX_SAMPLES and all(s.get("ok") for s in samples[-96:])),
    }


def _samples_in(samples: list[dict], start: str, end: str) -> list[dict]:
    return [s for s in samples if start <= s["at"][:10] <= end]


def window_status(samples: list[dict], start: str, end: str, today: str) -> dict:
    inside = _samples_in(samples, start, end)
    rule = ("SINGLE SHOT: AF has no durable host, and restarting on a fresh quick-tunnel URL changes the "
            "origin, so the observation is not comparable. If invalidated, the window ends: its numbers are "
            "a failure log about host capability, not a demand finding. A second window needs a durable host, "
            "which AF states as a capability gap.")
    if today < start:
        return {"status": "not_started", "starts": start, "uptime_pct": None, "invalidation_reason": None,
                "samples": 0, "restart_rule": rule}
    if not inside:
        return {"status": "invalidated", "starts": start, "uptime_pct": None,
                "invalidation_reason": "no probes recorded inside the window", "samples": 0,
                "restart_rule": rule}

    uptime = round(100 * sum(1 for s in inside if s.get("ok")) / len(inside), 2)
    worst_run, run = 0, 0
    for s in inside:
        run = run + 1 if not s.get("ok") else 0
        worst_run = max(worst_run, run)

    gap_min = 0
    for prev, cur in zip(inside, inside[1:]):
        a = datetime.strptime(prev["at"], "%Y-%m-%dT%H:%M:%SZ")
        b = datetime.strptime(cur["at"], "%Y-%m-%dT%H:%M:%SZ")
        gap_min = max(gap_min, int((b - a).total_seconds() / 60))

    reason = None
    if worst_run >= INVALIDATE_CONSECUTIVE_FAILURES:
        reason = f"{worst_run} consecutive failed probes (>= {INVALIDATE_CONSECUTIVE_FAILURES} invalidates)"
    elif gap_min > INVALIDATE_MAX_GAP_MIN:
        reason = f"{gap_min} minute gap between probes (> {INVALIDATE_MAX_GAP_MIN} invalidates)"
    return {
        "status": "invalidated" if reason else "active",
        "starts": start,
        "uptime_pct": uptime,
        "samples": len(inside),
        "worst_consecutive_failures": worst_run,
        "max_gap_minutes": gap_min,
        "invalidation_reason": reason,
        "restart_rule": rule,
    }


def main() -> int:
    if not ENDPOINT_FILE.exists():
        print(f"no endpoint file at {ENDPOINT_FILE}")
        return 2
    base = str(json.loads(ENDPOINT_FILE.read_text()).get("url") or "").rstrip("/")
    if not base.startswith("http"):
        print(f"endpoint file has no usable url: {base!r}")
        return 2

    sample = probe(base)
    health = {"generated_at": sample["at"], "endpoint": base}
    if HEALTH_FILE.exists():
        try:
            health.update(json.loads(HEALTH_FILE.read_text()))
        except Exception:
            pass
    samples = list(health.get("history") or [])
    samples.append({k: v for k, v in sample.items() if k != "status"})
    if sample.get("status"):
        # keep the last good catalogue so the status page still shows prices when the host is down
        Path("site/data/x402_status.json").write_text(json.dumps(sample["status"], ensure_ascii=False, indent=1))
    samples = samples[-MAX_SAMPLES:]
    health["endpoint"] = base
    health["history"] = samples
    health["summary"] = summarise(samples)
    health["proof_tx"] = health.get("proof_tx") or []
    today = sample["at"][:10]
    health["windows"] = {
        "A": window_status(samples, *WINDOW_A, today),
        "B": window_status(samples, *WINDOW_B, today),
    }
    health["generated_at"] = sample["at"]
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.write_text(json.dumps(health, ensure_ascii=False, indent=1))
    print(f"{sample['at']} ok={sample['ok']} checks={sample['checks']} "
          f"uptime={health['summary'].get('uptime_pct')}% p50={health['summary'].get('latency_p50_ms')}ms")
    return 0 if sample["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

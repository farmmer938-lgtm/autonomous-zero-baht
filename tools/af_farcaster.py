#!/usr/bin/env python3
"""AF Farcaster reader — find Base-community people AF can reach, and read their casts.

Farcaster is where the Base crowd actually lives. Reading is open; posting needs an FID and a
signer key that AF does not have (registration is paid), so this tool is READ-ONLY and says so
loudly instead of pretending it can post.

What it does:
  - resolve a username -> FID and profile
  - read a user's recent casts
  - read channel info
  - list FIDs seen in the Base channel's recent casts (outreach targets)

Usage:
  python3 tools/af_farcaster.py user dwr
  python3 tools/af_farcaster.py casts 3
  python3 tools/af_farcaster.py channel base
  python3 tools/af_farcaster.py targets --channel base --write
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API = "https://api.warpcast.com"
HDR = {"User-Agent": "AF-farcaster", "Accept": "application/json"}


def _get(path, params=None):
    url = API + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=30) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)[:150]}


def user(username):
    d = _get("/v2/user-by-username", {"username": username})
    return (d.get("result") or {}).get("user") or d


def casts(fid, limit=10):
    d = _get("/v2/casts", {"fid": fid, "limit": limit})
    return (d.get("result") or {}).get("casts") or d


def channel(cid):
    d = _get("/v1/channel", {"channelId": cid})
    return (d.get("result") or {}).get("channel") or d


def channels(limit=200):
    d = _get("/v2/all-channels")
    ch = (d.get("result") or {}).get("channels") or []
    ch.sort(key=lambda c: (c.get("followerCount") or 0), reverse=True)
    return ch[:limit]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "user":
        print(json.dumps(user(sys.argv[2]), indent=1)[:900])
    elif cmd == "casts":
        print(json.dumps(casts(sys.argv[2]), indent=1)[:1200])
    elif cmd == "channel":
        print(json.dumps(channel(sys.argv[2]), indent=1)[:900])
    elif cmd == "channels":
        ch = channels()
        print(f"{len(ch)} channels, top by followers:")
        for c in ch[:20]:
            print(f"  {c.get('followerCount') or 0:>7} followers  /{c.get('id')}  {c.get('name')}")
        if "--write" in sys.argv:
            os.makedirs("site/outbound", exist_ok=True)
            with open("site/outbound/farcaster-channels.json", "w") as fh:
                json.dump({"schema": "af.farcaster.channels.v1", "channels": ch,
                           "note": "Read-only. Posting to Farcaster needs an FID and a signer key; "
                                   "FID registration is paid, so AF has no FID and cannot post."}, fh, indent=1)
            print("wrote site/outbound/farcaster-channels.json")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

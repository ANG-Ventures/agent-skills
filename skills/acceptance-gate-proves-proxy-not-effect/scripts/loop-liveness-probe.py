import os
#!/usr/bin/env python3
"""SAFE loop-liveness AC probe for the Hermes dashboard event loop.

Proves "the event loop stays responsive while a heavy read runs" WITHOUT DoS-ing the live
service: ONE modest poller of a heavy endpoint + a trivial-endpoint latency probe. If the
trivial probe stays low while the heavy read runs, the loop is not stalling — invariant
proven, zero risk. Do NOT add GIL-churn threads / connection floods against a live backend
(see the parent SKILL.md: the destructive live gate).

Auth gotchas learned the hard way (all baked in below):
  - login is POST /auth/password-login  (NO /api prefix; the /api-prefixed one 401s)
    body {"provider":"basic","username":U,"password":P}, creds from the harness secrets file
    (HERMES_DASHBOARD_BASIC_AUTH_USERNAME / _PASSWORD; strip surrounding quotes)
  - ws ticket is POST /api/auth/ws-ticket  (data=b"", method POST) -> {"ticket": ...}
  - ws connect: pass the auth Cookie header; do NOT add your own Origin header (the client
    library adds one from the URL; a second value -> 400 "multiple values; 'Origin'")
  - to read a session.list reply, DRAIN frames until m["id"]==your rid (async event frames
    interleave); set ws.settimeout so a missing reply can't block forever.

Run: ~/.hermes/runtime/hermes-agent/venv/bin/python loop-liveness-probe.py
"""
import json, os, re, time, threading, http.cookiejar, urllib.request

BASE = os.environ.get("HERMES_DASH_BASE", "http://mac-studio-m3u:9119")
env = open(os.path.join(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"), ".env")).read()
U = re.search(r"HERMES_DASHBOARD_BASIC_AUTH_USERNAME=(.*)", env).group(1).strip().strip('"\'')
P = re.search(r"HERMES_DASHBOARD_BASIC_AUTH_PASSWORD=(.*)", env).group(1).strip().strip('"\'')

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request(BASE + "/auth/password-login",
    data=json.dumps({"provider": "basic", "username": U, "password": P}).encode(),
    headers={"Content-Type": "application/json"}, method="POST"), timeout=60).read()
print("[auth] ok")

stop = threading.Event()
def heavy_poller():           # ONE modest poller — NOT a hammer, NOT a flood
    while not stop.is_set():
        try: op.open(urllib.request.Request(BASE + "/api/sessions/stats"), timeout=60).read()
        except Exception: pass
        time.sleep(0.3)
threading.Thread(target=heavy_poller, daemon=True).start()

trivial = []
for _ in range(40):
    t0 = time.time()
    try:
        op.open(urllib.request.Request(BASE + "/api/auth/providers"), timeout=10).read()
        trivial.append(time.time() - t0)
    except Exception:
        trivial.append(10.0)
    time.sleep(0.1)
stop.set(); time.sleep(0.4)

trivial.sort()
p50 = trivial[len(trivial)//2] * 1000
p99 = trivial[min(len(trivial)-1, int(len(trivial)*0.99))] * 1000
mx = max(trivial) * 1000
ok = p99 < 1000 and mx < 5000
print(f"\ntrivial /api/auth/providers WHILE heavy stats poll runs:")
print(f"  p50={p50:.0f}ms p99={p99:.0f}ms max={mx:.0f}ms")
print(f"LOOP-LIVENESS: {'PASS ✅ (loop stays live under load)' if ok else 'FAIL ❌ (loop stalling)'}")
print("  (a stalled loop spikes this to seconds; a healthy one stays ~10ms)")

<!-- vendored 2026-07-03 from local overlay skill `acceptance-gate-proves-proxy-not-effect-local` (background-curation session was read-only to skills-shared/external_dirs; folded into this master per skill-hygiene) -->

---
name: acceptance-gate-proves-proxy-not-effect-local
description: "LOCAL addendum to the read-only shared skill `acceptance-gate-proves-proxy-not-effect`. Load BOTH when about to run a LIVE acceptance/E2E gate — especially a load/stress/concurrency AC — against a shared, user-facing service (dashboard, gateway, live backend). Carries the destructive-live-gate pitfall the shared skill can't hold (external_dirs is read-only to autonomous curation): don't generate the outage you're certifying against; prove the invariant with a light representative probe on a disposable/seeded target; a green invariant beside a surfaced-separate slowness is an honest PASS. When the shared skill becomes writable, fold this in and delete this."
---

# Acceptance gate proves proxy, not effect — LOCAL addendum

Companion to shared `acceptance-gate-proves-proxy-not-effect` (read-only, external_dirs).
Load the shared skill for the proxy-green taxonomy; load THIS for the inverse failure —
a gate that is *too real against the wrong target* and causes the outage it's meant to
certify against. Verified 2026-07-03 (dashboard event-loop AC-2).

## The DESTRUCTIVE live acceptance gate — the test causes the outage it certifies against

When an AC is "the system stays responsive under load," the naive gate generates that stress
**against the LIVE production instance the user depends on**. If the fix is imperfect (or the
synthetic load is harsher than real load), the gate takes down the very service it's proving.
Verified: I ran an incident-regime load script — 3 CPU-pegging GIL-churn threads +
connection-flood ws bursts + stats hammers — against the user's **live** dashboard backend; it
coincided with a SIGKILL/restart of the process his MacBook was actively connected to.
Testing overload-resilience by overloading the thing in use is backwards.

### Tells (any one = STOP before running)
- The AC's stimulus is *load/stress/concurrency* and the target is a **shared, live,
  user-facing** service (not a disposable/staging instance).
- Your own spec already prefers a **gentler load model** — the PRD said prefer "3 live agent
  turns" over synthetic CPU threads *because synthetic is harsher*. If the doc warns the harsh
  variant is unrepresentative, don't reach for it against production. Read your own D-4/RR2
  before hammering.

### Do instead — prove the INVARIANT without generating the outage
- **Separate the invariant from the stimulus.** AC-2's invariant was "the event loop stays
  live under a slow read" — NOT "the loop survives a DoS." Prove it with a **light,
  representative** concurrent probe: ONE modest poller of the heavy endpoint while a
  trivial-endpoint latency probe runs. If the trivial endpoint stays ~10ms *while* the heavy
  read runs, the loop is not stalling — invariant proven, zero risk. A stalled loop would
  spike the trivial probe to seconds; a healthy one won't. That contrast IS the proof.
- **You may already have the safe evidence.** Before writing a stress test, check whether
  earlier measurements already establish the effect (here: stats `15s→81ms`, trivial `10ms`
  under a modest hammer were captured safely earlier — the destructive re-test was never
  needed).
- **If you must generate real load, target a disposable/seeded instance, never the shared
  live one.** For per-session features: seed a throwaway session (`session.create`), drive
  the gate on it, delete it (`session.delete`), then verify no litter remains — query real
  session rows by title; an FTS hit on your own on-disk script text is NOT a leftover row.
- **Record the miss honestly in the PRD** if you tripped it — "ran harsh synthetic load
  against live, caused a restart, re-ran gently" is a documented process note, not buried.

### Corollary — a green invariant + a surfaced-separate slowness is an honest PASS
AC-2's loop-liveness passed live even though a *different* call (`session.list` ~2s) was slow:
the trivial probe staying at 10ms *during* it PROVED the slowness was handler-local (off-loop
projection cost over a large session store), not loop starvation. Don't fail the gate for a
pre-existing adjacent cost you never touched — prove it's separate (the concurrent-trivial-
probe contrast does this), file it as a residual/follow-up, and pass the gate on its actual
invariant. (When the fork has issues disabled, the "follow-up" goes in the PRD residuals
section, not a tracker.)

## Support file
- `scripts/loop-liveness-probe.py` — the SAFE probe itself, ready to run
  (`~/.hermes/runtime/hermes-agent/venv/bin/python .../loop-liveness-probe.py`). Auth quirks
  baked in: login is `/auth/password-login` (NO /api prefix — /api-prefixed 401s); ws-ticket
  is `/api/auth/ws-ticket`; do NOT add your own ws `Origin` header (client adds one → a
  second value 400s). One modest heavy poller + trivial-latency probe; prints PASS/FAIL.

## When the shared skill becomes writable
Fold the above into `acceptance-gate-proves-proxy-not-effect` (as a new sub-species:
"the destructive live gate") and delete this local addendum (plus its `scripts/`).

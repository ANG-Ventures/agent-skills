# Per-path probing: an AGGREGATE "everything's failing" hides per-path truth — and a generic probe lies

When a system fans work across **several interchangeable paths** — egress lanes/proxies, DB
replicas, API backends, CDN POPs, worker pools, retry mirrors — and it stops making progress,
the instinct is to reach for a single global story: *"we're rate-limited," "the upstream is
gating us," "just wait it out / rest it a day."* That story is almost always **wrong and
expensive**, because two distinct illusions stack on top of each other:

1. **The orchestrator's own give-up message masquerades as the upstream's rejection.** A
   governor/circuit-breaker/load-balancer that cools or skips a path emits its OWN status
   (`all lanes cooling`, `circuit open`, `no healthy upstream`, `pool exhausted`) — and that
   status gets recorded as the item's "failure." Counting those as upstream rejections wildly
   overstates how blocked you actually are. **Most "failures" can be your code declining to try,
   not the remote saying no.** (Real case 2026-06-13: 90% of 7,431 "failed" items were our
   governor's `all lanes cooling` — never actually attempted against the server.)

2. **Paths fail INDEPENDENTLY — "everything is blocked" is rarely literally true.** When the
   fan-out logic cools the good path along with the bad ones (shared governor, global backoff),
   a single working path is invisible behind the aggregate. (Real case: 3 house IPs were
   genuinely bot-gated by YouTube while the 4th lane — a cell/mobile IP — downloaded fine the
   whole time; the multi-lane governor cooled the working lane too, so "nothing downloads"
   looked total when one path worked.)

## The rule: actively probe EACH path against a REAL workload item

Don't reason about which path is blocked — **test each one, in isolation, right now**, by
running the real operation (not a `/health` ping, not a HEAD request) through that single path
and reading the actual result. Classify each path into an **actionable verdict with a remedy**:
works / blocked-by-upstream / auth-bad / path-down(our side) / dead-item / rate-limited /
unknown — and crucially distinguish **our-side faults** (tunnel/proxy/connection down) from
**upstream faults** (bot-gate, 429) from **content faults** (the item itself is gone). A
one-command per-path doctor turns a multi-hour misdiagnosis into a 3-minute answer, then you
route the work through whatever path verdicts `works`.

## The probe input MUST be representative — a generic/popular item gives a FALSE GREEN

The subtlest trap: validating a path (or cookies/auth, or "is the service even up?") against a
**generic, popular, cached, or trivially-served item** passes even when the **real workload**
is blocked. A popular video / a `/health` route / a well-known public record is on a fast,
unguarded path; your actual corpus items hit the guarded path. So a cookie-refresh job, an
uptime check, or a smoke test that probes the easy item reports **"ok" for days while every
real request fails**. (Real case: the YouTube cookie-refresh cron validated against a
3Blue1Brown video that always downloads — so it stayed green while every corpus video was
bot-gated. Fix: probe with a *real pending item pulled from the actual work queue/manifest*.)

**Rule:** any validation/health/smoke probe for a workload must use a **representative item
drawn from the real backlog**, never a hand-picked generic one. If `validate()` can't fail when
the workload is failing, it isn't validating — it's theater.

## Don't thrash; don't "rest it a day" before you've probed

"Let it rest / wait for the gate to clear" is a real remedy **only after** a per-path probe
confirms genuine upstream blocking on that path. Reaching for it *first* — or restarting/killing
the orchestrator repeatedly — wastes hours and (for resumable jobs) manufactures the flat-progress
symptom you're chasing (see §5d in the main skill). Probe first, then rest the genuinely-blocked
paths while routing through the working one.

## Make the diagnosis a re-runnable tool, not a one-time investigation

The instrumentation outlasts the bug (the master-skill principle). Build the per-path doctor as
a committed script with a verdict taxonomy that **reuses the live system's own classifier** (so
the bot-gate-vs-dead-vs-ratelimit rules can't drift from production), plus tests for the
discriminating pairs (e.g. a real bot-gate vs a "Private video / Sign in" dead item — both
contain "Sign in" but mean opposite things). Then the next session runs one command instead of
re-deriving the whole thing. (Worked example: `youtube-notebooklm`'s `src/lane_doctor.py` +

## Quick checklist when a fan-out pipeline "isn't progressing"

- [ ] Is the recorded "failure" the UPSTREAM's word, or our own governor/LB giving up? (read the
      actual error strings, not the counter)
- [ ] Probe EACH path independently with the REAL operation — not a health ping.
- [ ] Use a REPRESENTATIVE workload item as the probe, never a generic/popular one.
- [ ] Classify each path: works / upstream-blocked / auth-bad / our-path-down / dead-item /
      rate-limited — with a remedy each.
- [ ] Route work through the `works` paths; rest only the genuinely-blocked ones.
- [ ] Capture the probe as a re-runnable tool reusing the prod classifier, so it's a 3-minute
      command next time.

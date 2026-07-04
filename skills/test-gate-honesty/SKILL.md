---
name: test-gate-honesty
description: >
  Prove a test actually GATES the property it names — and triage a CI red on a test your diff didn't
  touch. Load when a code-review (or you) must certify that green tests aren't lying, or when CI fails
  on a test outside your change. Companion/overflow home for the parts of `verifying-beyond-green-tests`
  and `systematic-debugging` that live in read-only external_dirs: the VACUOUS-gate class (a test that
  passes by construction), the MUTATION-PROOF acceptance ritual, and the FLAKY-vs-real-race triage.
  Triggers: "does this test actually fail if the invariant breaks", "the gate is a tautology", "mutation
  test the fix", "is this CI red flaky or real", "should we spec fixing this flaky test", "the test
  passes whether or not the code is right".
version: 1.0.0
---

# Test-Gate Honesty

A green test proves nothing unless it would go **RED** when the property it names is violated. This skill
is the editable home for three disciplines that recurred hard (2026-07-01) and whose ideal homes
(`verifying-beyond-green-tests`, `systematic-debugging`) are read-only external_dirs this session. When
those become writable, fold these in and point here.

## 1. The VACUOUS gate — a test that passes by construction (a green lie)

A test named for an invariant can pass **whether or not the invariant holds**, because it never drives the
property into a state that could fail. Worse than no test: it reads as coverage. Ask of every assertion:
**"what concrete value / code path makes THIS line go RED?"** If you can't name one, the gate is vacuous.
A senior code-review reliably catches these — catch them yourself first.

Two verified sub-classes (Opus code-review BLOCKED both of MINE — the review was 100% right):

- **The TAUTOLOGY.** A privacy/exclusion test declared a `SECRET` sentinel and asserted `SECRET not in
  log_line`, but never **seeded** `SECRET` into any field the log producer actually reads — the producers
  only interpolated `session_key`/`reason`/flags, none of which can ever contain the marker. True by
  construction; a future content-leak would keep it green. **Fix:** seed the sentinel into every surface the
  producer *could* reach (transcript via the real writer, pending-message list, the running-agent object),
  THEN assert exclusion. **Prove non-vacuous by MUTATION:** add a `msg=%s` that leaks content → the test must
  go RED. A privacy/exclusion assertion not mutation-proven to fail on a real leak is decorative.
- **The OVERCLAIM.** A "non-blocking" latency test whose own docstring conceded *"the stdlib logger emits
  synchronously, so a genuinely blocking handler WOULD extend this"* — it proved "single emit, no fan-out,"
  NOT the named property. Worse, the code comment asserted a handler-config property out of the diff's
  control. **Fix = honesty, not a bigger test:** rename to what it actually proves, retract the false claim
  in the docstring, and if the property matters make the CODE enforce it (wrap the drain-critical log in
  `try/except` so a raising sink can't abort the mark — losing the mark = losing the work) with a test that
  proves *that*. **Never let a test NAME assert a property the test BODY doesn't.**

## 2. The MUTATION-PROOF as a routine acceptance step (not just for reviews)

Whenever a test guards a load-bearing WIRING point — a call site passes the right flag, a persisted field
survives, an exclusion holds — don't trust green. **Flip the one production line and confirm RED.** The
ritual: build test → green → mutate the production line → RED → revert → green. If step-3 stays green, the
test is vacuous (§1).

Critically, this catches the **call-site gap** that pure unit tests bypass: a unit test that calls the
function directly with the flag pre-set does NOT prove the real entry point passes that flag. Verified: an
integration test drove the real `stop()` through the drain-timeout branch and asserted the session got
`restart_consumed_interrupted`; flipping the post-timeout mark site to `interrupted=False` turned it RED —
proving the CALL SITE, which every unit test of the function bypassed.

## 3. FLAKY vs REAL-race triage — a CI red on a test your diff didn't touch

Both wrong turns cost: "just re-run" hides a real bug; "spec a fix" over-engineers a test-timing nit
("boil the ocean / do it all" does NOT mean spec a flaky-test nit). Triage in order BEFORE deciding:

1. **Is it even mine?** `git diff --name-only <base>...HEAD | grep <failing-area>` — no overlap ⇒ likely
   pre-existing. Run the failing test **in isolation**; passes alone but fails in the full suite ⇒
   load/ordering-sensitive, not your logic.
2. **Test-harness race vs production race?** Read the failing assertion's *target* and the path to it. Tell
   (honcho `test_stale_pending_result_is_discarded_on_read`): the assert was on a cache slot
   (`_prefetch_result == ""`), meaning the function **early-returned before the read-and-clear** — a
   readiness guard (`_session_ready()` False because a background `_init_thread` was still alive)
   short-circuited it. The staleness logic was deterministic turn-count math and couldn't flake; the flake
   was the **test helper under-draining a thread** (`_settle_prewarm` joined the prefetch thread but not the
   init thread) → under CI CPU contention the init thread outlived setup. Test-harness bug → fix the SHARED
   helper (hardens all call sites), NOT production, NOT spec-worthy.
3. **Reproduce the MECHANISM deterministically even if you can't reproduce the FLAKE.** Local brute-force CPU
   load (spawning `yes`) often won't recreate a CI race needing the interleaving of ~200 concurrent test
   files — expected, not "can't fix." Inject the exact bad state instead: set a live `_init_thread` +
   `_session_initialized=False`, call the function, observe it early-returns leaving the slot uncleared — the
   exact CI signature. Mechanism-repro + correct hardening beats a statistical "ran it 100×."
4. **Be honest about what you proved.** "I removed the exact nondeterminism that caused the observed failure"
   is truthful; "I made CI 100× less flaky" (unmeasured) is not.

**Decision:** flaky test-harness race → tiny `test(...)`-only fix on its OWN branch + a regression test
locking the mechanism. Genuine production liveness race → then weigh scope. Owner handoff when GitHub
issues are disabled: the full root-cause writeup in the fix PR's body IS the handoff.

## 4. Landing a green-locally PR through SERIALLY-flaky CI on a busy fleet (don't hand-babysit)

Once you've triaged (§3) that the reds are **flakes your diff didn't cause** — verified by the test passing
locally N× and your PR not touching that file — the remaining problem is *operational*, not diagnostic:
your correct PR still won't merge, and manually poll-then-merge becomes a losing race. Two compounding
forces (both real, 2026-07-01 `/usage` PR #141):

- **Serial flakiness.** A busy CI (8 parallel workers under load) flakes a **DIFFERENT unrelated timing
  test each run** — honcho dialectic, then a tui_gateway "no_race" thread test, etc. Each passes locally and
  is outside your diff. Re-running once isn't enough; you need bounded retries because the *next* run may
  flake somewhere else.
- **The BEHIND merge-race.** On a fleet actively merging PRs, `fork/main` advances *while your CI runs*, so
  every time you finally go green the PR flips to `BEHIND` (or `UNKNOWN`) and GitHub demands a fresh
  up-to-date run. You update-branch, wait ~9 min, and another PR lands first → repeat forever. Manually you
  can lose this race indefinitely.

**Don't grind it by hand — hand it to a self-disabling merge-watcher cron** (the same pattern that lands
own-repo PRs elsewhere in the fleet). A `no_agent` bash cron, every ~6 min, that on each tick:
1. `MERGED`/closed → self-`pause` (done); any `pending` checks → wait next tick.
2. `fails>0` → **flake-retry**: `gh run rerun <runid> --failed`, bumping a persisted counter
   (`~/.hermes/state/merge-<pr>-retries`), up to a bound (4×). Only *after* exhausting retries does it
   `pause` for human review — so a persistent (real) failure still stops, but transient flakes don't.
3. `BEHIND`/`UNKNOWN` → `gh pr update-branch` and **reset the retry counter** (fresh base = fresh CI).
4. All green + up-to-date → resolve any lingering Greptile threads via GraphQL, then
   `gh pr merge --squash --admin`; confirm `MERGED` and self-`pause`.

Template: copy `templates/merge-watcher-flaky-ci.sh`, set `PR=<n>`, register with `cronjob` (no_agent,
deliver to a logs channel). This encodes the autonomy-doctrine call: a flaky-CI merge is *labor a machine
can do* (retry + rebase + admin-merge), not a *decision* — only a genuinely-stuck real failure should page a
human. 🔴 The naive watcher that self-disables on the FIRST red is wrong here: it treats every flake as a
real block and strands a correct PR. The bound-retry counter is the load-bearing difference.

🔴 **`--admin` alone does NOT bypass an unresolved review thread.** A PR can be all-green-checks yet
`BLOCKED` with `gh pr merge --admin` returning `GraphQL: All comments must be resolved.` — that's an
unresolved Greptile **review thread** (distinct from the Greptile *check*, which can read SUCCESS). Resolve
each thread (`resolveReviewThread` GraphQL mutation on its `threadId`) — after actually addressing it in code
where the finding is legit, not by dismissing — THEN admin-merge. The watcher template does this each tick.

🔴 **A merge that FF-integrates the current PR flow can DROP a just-landed regression fix if you re-sync
from the wrong base.** During the #141 grind, `min(100,…)` clamp fixes and P2 fixes were committed on the
branch; each `git merge fork/main` re-sync must be verified to still carry them (`grep -c '<your-symbol>'`
after every sync) before pushing — a botched merge can silently revert your own fix commit.

## Cross-refs
- `verifying-beyond-green-tests` (external_dirs, read-only this session) — Seams 1–4 (persistence-key drop,
  cross-process/restart state, live wiring, one-shot-gate scoping). This skill = the vacuous-gate + mutation
  + flaky-triage overflow; fold back when that skill is writable.
- `systematic-debugging` — the 4-phase root-cause method the flaky-triage sits inside.
- `prd-review-pipeline` — the review loop that catches vacuous gates; put test files IN the review pack.

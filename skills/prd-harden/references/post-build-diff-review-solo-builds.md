# Post-build senior diff-review on SOLO builds (not just swarms)

The senior Opus diff-review of the *integrated code* (`prd-review-pipeline` §2.8.1,
`prd-swarm-plan` §2.8) is usually framed as a **swarm** step — run it after fanning
out workers. **It is just as load-bearing on a SOLO build you wrote yourself**, and is a
first-class hardening gate. Proven 2026-06-12 building the cron-observability stack solo:
48 unit/integration tests green, then a single Opus diff-review returned **BLOCK** with a
stack of silent-failure-class bugs no green test caught. Run the diff-review on any non-trivial
built system before closeout, swarm or not.

## Why solo builds need it MORE, not less
A swarm's bugs cluster at cross-worker seams. A solo build's bugs cluster where **you reused
your own mental model across modules** — the exact place your own tests inherit the same blind
spot. You wrote the producer, the consumer, AND both their tests, so a contract mismatch is
invisible: the test asserts what you *meant*, the same thing the code does. An independent
reviewer reading the integrated diff reasons from the code, not your intent.

## The bug class to hunt: silent-failure seams in OBSERVABILITY/WATCHER code
The most dangerous place for a green-tests-pass-but-broken bug is code whose **whole job is
catching silent failures** — a watcher, a healthcheck, a detector, an alert router, a backup
verifier. A silent-failure seam bug *there* means the thing that's supposed to catch silent
failures itself fails silently. Tell the reviewer this explicitly: "this system exists to catch
silent cron failures, so a silent failure IN it is the worst outcome — hunt any path where a
real broken job produces NO finding, or a finding never reaches the alert channel." Real catches
from that one prompt (all green-tests-passing):
- A recovery announced **"recovered" for a job that was broken right now** (the alert lied about
  state — the single worst outcome for a state watcher). Root cause: recovery truth-source was a
  stale cross-tick snapshot, not the live detector.
- A wrapper that could **manufacture a false "STUCK" alert** because a polluted stdout capture
  broke the run-finalize, leaving a perpetual "running" row.
- **Error-swallow**: a job that errored then succeeded between two polls recorded only the
  success — the error vanished from a silent-failure detector.
- A storm cap that suppressed the **11th distinct new break during a real incident** (per-source
  cap instead of per-key) — blind exactly when you need it most.

## The blind-spot that survives BOTH the diff-review AND the unit suite: an unreachable predicate per job-shape (2026-06-12, found at CLOSEOUT)
The diff-review + 65 unit tests + a 17-probe adversarial dogfood battery all passed, and a
**real, high-severity detector blindspot still shipped** — caught only at `prd-closeout` by
ground-truthing a live finding against disk. This is the sharpest version of the watcher-bug
class: not a logic error, a **gating-order** error.

The cron detector evaluated findings in this order: `_skip` → `has_running` → compute
`stale_deadline` → **`if deadline == inf: continue`** → … → FAIL check. The FAIL rule ("last
terminal run errored") sat AFTER the `deadline == inf` early-`continue`. So any job whose
`expected_interval_sec` is NULL (no computable cadence) hit `deadline == inf` and was skipped
**before the FAIL check ever ran** — meaning a job erroring on EVERY run (136× in a row, live)
produced **zero findings and never paged anyone.** 15 live wrapped jobs had NULL intervals and
were all blind to error detection — the exact silent-failure the whole system exists to catch.

Why everything green missed it:
- **The unit tests all used a fixed interval** (`_periodic(conn, jid, 3600, …)`) — none exercised
  the NULL-interval shape, so the FAIL test passed while the NULL-interval-FAIL path was dead.
- **The dogfood battery's probes also set an interval** — same blind spot, inherited from the
  same mental model ("a periodic job has an interval").
- **The diff-review reasoned about the FAIL *logic* (which was correct)**, not about whether the
  FAIL branch was *reachable for every job shape*. Reachability-per-input-shape is a different
  question than per-branch correctness, and it's the one a happy-path reviewer skips.

**The durable rule:** in any detector/router/classifier, an alert/finding for a **terminal
failure state** (errored, dead, down) must NOT be gated behind a predicate that can be *absent*
or *unknown* for a legitimate input (a NULL interval, a missing schedule, an unparseable
cadence). Evaluate the terminal-failure check FIRST and make it **independent of the
optional/derived fields**. A staleness/overdue check legitimately needs a cadence; an
*it-errored* check never does.

**How to hunt it (add to the diff-review prompt + the hardening gap-table):**
1. For every early-`continue`/`return`/guard in the evaluation loop, ask: "which input shapes
   hit this guard, and what findings can they NO LONGER produce after it?" An early `continue`
   on a *derived/optional* field (interval, deadline, parsed timestamp, computed score) is the
   prime suspect — it silently removes a whole input class from later checks.
2. Enumerate the **field-presence matrix** of real registry rows (`SELECT count(*) … WHERE
   <optional_field> IS NULL`) — a non-zero count on a field that gates a terminal-failure check
   is a live blindspot, not a hypothetical.
3. Add a regression test PER optional-field-absent shape (here: NULL-interval-erroring → MUST
   FAIL; NULL-interval-ok → must NOT flag), RED-proven by reverting the reorder.

The cheap detector that would have caught it at build time: a **field-presence-matrix dogfood
probe** — for each finding type, construct an input with each optional field NULL/absent and
assert the finding still fires when it should. (The dogfood battery's lesson: vary the
*input-shape* axis, not just the value axis. Fixed-interval probes can't catch an interval-gated
blindspot.)

## A TIME-WINDOWED staleness watchdog has its own recurring 5-bug checklist (2026-06-12)
Building a "did the scheduled job fire?" watchdog (poll/cron/heartbeat liveness keyed off a
clock cadence) is its own sub-class of the watcher bug family, and a solo build + a passing unit
suite reliably ships ALL of these — the Opus diff-review caught 5 in one pass on a 22-green build.
Hunt each explicitly, in the code AND the schedule:

1. **Schedule-vs-detector slot mismatch (the headline).** If the detector returns "the most recent
   due slot" but the watchdog is *scheduled once/day*, it can only ever certify the LAST slot — the
   earlier slots' misses are caught only as a side-effect of also missing the last one. The
   detection function and the launchd/cron schedule must AGREE on granularity: schedule the watchdog
   **after each slot+grace** (N runs for N slots), OR have one run assert *every* slot due-so-far
   was satisfied. A once-daily run against a single-most-recent-slot detector is structurally blind
   to per-slot misses. Check the plist `StartCalendarInterval` count against the slot count.
2. **DST construct-time-offset.** Building a slot as `datetime(y,m,d,hour, tzinfo=ZoneInfo(...))`
   bakes a possibly-wrong UTC offset, and `slot + GRACE` then does *wall-time* arithmetic. On the
   ~2 transition days/year the window shifts 1h → false-fire OR late-detection. Fix: build a **naive**
   wall-clock time, then `naive.replace(tzinfo=PT).astimezone(UTC)`, and do ALL comparisons on
   absolute UTC instants. Add a DST-transition-day test (both a fire and a no-false-fire case).
3. **Timezone-DB-missing → silent UTC degrade or uncaught crash.** A `try: PT=ZoneInfo(...) except: PT=None`
   fallback that then builds naive slots and compares them to an aware `now` throws an uncaught
   `TypeError` (a blind watchdog) — or, if it "works," silently shifts every slot 7-8h. Make the
   missing-tz path **fail LOUD** (alert "watchdog blind, no tzdata"), never guess the cadence in the
   wrong zone.
4. **Liveness keyed off "woke up" not "succeeded" (the most dangerous).** If the collector stamps a
   `last_poll_at` on EVERY run (incl. errored) but only advances `last_successful_poll` on success,
   a watchdog comparing the slot against `last_poll_at` judges an **erroring-but-awake** collector
   healthy — the single most likely real failure (process runs, work fails) is invisible. Key the
   liveness gate off the **success** timestamp. Mind the type difference (`last_successful_poll` is
   often a float epoch; `last_poll_at` an ISO string). Distinguish "never polled" (day-0 quiet) from
   "polled but never succeeded" (real stall, report honestly as NEVER — don't fabricate epoch math).
5. **The alarm's own delivery path swallows failures.** `_alert` wrapping `subprocess.run([notify…])`
   in `try/except: pass` with `capture_output=True` means: watchdog correctly detects the stall,
   notify fails (missing script, wrong interpreter, rejected channel), and the operator hears
   NOTHING — the silent-failure class reproduced one layer down, in the alert delivery itself. On
   non-zero return OR exception, `print(... file=sys.stderr)` (launchd captures it) AND drop a
   `*-alert-failed.json` sentinel. Never `pass`. Also reconcile the interpreter: a wrapper calling
   `/usr/bin/python3 notify.py` while the rest of the system runs a venv `python3.11` can fail if
   notify imports anything non-stdlib.

Prove the whole chain with a **real controlled fire**: point the watchdog at a temp stale state +
the real config (so ALERTS resolves to the real channel), run the REAL `check()` → REAL notify →
confirm the alert landed in the alert channel, then DELETE the test alert. Unit tests mock the send;
only a real fire proves the delivery path. (Same "stage the real proof, then clean up" discipline as
the dry-run e2e.)

## Instrument-FIRST can overturn the spec's own "REAL BUG found" at build time (2026-06-12)
A spec written from observation can carry a *wrong* root-cause hypothesis, and the build's Phase-0
instrument-before-fix step is where you catch it — the build-time analog of `prd-review-pipeline`'s
"ground-truth the premise." This session the spec's ground-truth block confidently stated a "REAL
BUG: the collector's declared log files don't exist → logging is broken." Phase-0 (`launchctl print`)
showed `runs=0, last exit=(never exited)` — the launchd job had simply **never fired yet** (loaded
one minute after its last scheduled slot); logging was fine, a `kickstart -k` immediately created the
logs with real content. Had the build followed the spec and "added an echo," it would have edited
*working* code to fix a non-bug. **Rule: when a spec/PRD hands you a named "the bug is X" hypothesis,
treat it as a hypothesis to falsify with a cheap probe BEFORE writing the fix** — `launchctl print`
for launchd state, the real state file's mtime + provenance, `runs`/`last exit` counters. A spec's
own ground-truth block is exactly the kind of confident-but-stale premise that instrument-first
exists to catch, and discovering "this isn't the bug" reshapes what the build should actually do.

## Multi-pass the BUILD, not just the spec — each fix round opens the next round's findings
The review→fix→re-review loop applies to code, and it converges the same way as the spec loop:
**the Pass-1 fix itself introduces the Pass-2 finding.** This session, the BLOCK-2 recovery fix
(retry suppressed recoveries across ticks) introduced ND-1 (a retained recovery could fire for a
job that re-broke) and ND-2 (unbounded `pending_recoveries` growth). Budget at least:
build → Pass-1 (expect BLOCK on a real system) → fix → Pass-2 verify (expect 1–3 *new* defects
from the fixes) → fix → (focused Pass-3 delta if Pass-2 fixes were heavy). Don't read "Pass-2
found new bugs" as the loop failing — that's the loop doing its job, identical to the spec-review
discipline in `prd-review-pipeline`.

## Most "a test failed" moments here were TEST bugs, not product bugs
Per `prd-review-pipeline`'s "empirically verify before fixing" rule, applied to your own tests:
when a freshly-written hardening test goes red, the **test** is the prime suspect, not the code.
This session, several red tests were test bugs: two fixtures sharing the same timestamp (→ same
PK → one overwrote the other), an assertion checking the wrong secret string, and a scenario that
was physically impossible (rewinding `jobs.json` doesn't re-break a job because the ledger retains
the fresh run). Each looked like a product failure for a moment. Read the failure, confirm whether
the *test* models reality correctly, THEN decide if the product is wrong. A test that asserts an
impossible sequence is a broken gate, not a found bug.

**A passing test suite can hide a STALE FIXTURE the moment you harden the system under it (2026-06-12, found at closeout).** When the hardening adds a new requirement to a shared helper — a deadman that now *also* watches a new heartbeat, a validator that now requires a new field — a pre-existing test fixture that predates the requirement will trip it, and the failure looks like a code regression. Real catch: hardening the backup-deadman to watch the restore-drill heartbeat made the deadman's own "fresh/silent" test fixture (which never wrote `last-success-restore-drill`) correctly-but-unexpectedly alert → exit 1, no output (`set -euo pipefail` died before the first echo). The fix is the **fixture**, not the code: add the new heartbeat to the shared `write_heartbeats` setup, AND add a *targeted* stale-case test for the new watch (don't leave a comment promising a case that doesn't exist — write it). Closeout's "run the suite, don't trust the last green" rule is what surfaces this; a silent `exit 1` from a `set -e` bash test means it died before its first `echo` — trace with `bash -x` to find the real failing line, don't trust the empty output.

ALSO: the adversarial dogfood battery's first "3 BUGS FOUND" run (2026-06-12) was the HARNESS
bypassing the schema — raw `INSERT INTO runs` omitting a `NOT NULL` column, which the schema
correctly rejected. The fix was to drive the REAL ingestion API (`upsert_run`), not to "fix" the
product. A probe that bypasses the real write path tests the bypass, not the system. Same
test-is-the-prime-suspect discipline.

## Hermetic isolation for a side-effecting watcher (the deadman pattern)
The cron-health **deadman** (fires the alerts channel when the observer stops) had ZERO automated tests —
only a manual dry-run — because it (a) reads module-global state-file paths and (b) calls
`notify.py` (a REAL Discord send). That's the `hermetic-test-isolation-side-effecting-functions`
class. Fix that made it testable without firing real alerts or sleeping 60s: give the function
**injectable seams defaulting to prod behavior** — `heartbeat_path`, `state_path`, `sender`,
`sleep_fn`, `wake_check` — and have it **return the alert message** (a testable signal) instead
of only side-effecting. The live `main()` call path passes nothing, so prod is unchanged; tests
pass temp paths + a fake sender + a no-op sleep. 8 RED-proven tests (fresh/stale/missing/dedup/
sleep-suppress/recheck-recovery/dry-run-never-sends/**real-state-byte-identical-after-run**).
The last test is the hermetic proof: assert the real `~/.hermes` state file's mtime is unchanged
after the suite runs. RED-proven by flipping the staleness comparison → 3 tests fail.

## Feed the reviewer a REDACTION-SAFE pack, or you'll chase a phantom BLOCK (2026-06-12)
The harness secret-redactor rewrites secret-shaped literals (`$(tr -d …)`, `Bearer <tok>`, a private
IP) to `***` **in the evidence-pack text the reviewer sees** — but the bytes on disk are correct. A
reviewer reading the masked pack reasons "this bash line is corrupt / this header is broken" and
returns a confident **false BLOCK**. Real catch: a restore-drill's `OP_SERVICE_ACCOUNT_TOKEN`-export
line (a `$(tr -d '\n\r' < "$TF")` read from a token file) showed masked in the pack → Pass-1 BLOCK-1
"corrupt bash," but `od -c` + `bash -n` + a live exit-0 launchd run all proved the bytes were fine.
Hours of phantom-chasing avoided only by ground-truthing the actual file.
**Rule:** before sending the pack, either (a) build it from a source the redactor doesn't mask, or
(b) annotate any `***`-bearing line: "this line contains a redaction-masked secret literal; on-disk
bytes are verified correct (`bash -n` clean, runs exit 0) — do NOT flag it as corrupt." When a
diff-review BLOCK lands on a secret-handling line, **verify the disk bytes (`od -c` / `bash -n` / a
live run) FIRST** before treating it as a real finding — a masked literal is the prime suspect.

## The preflight/healthcheck that SPENDS the budget it protects (the preflight paradox, 2026-06-14)
A health-check placed *before* a rate-limited operation can **consume the very budget it's checking
for**, and thereby CAUSE the failure it exists to detect. Real catch (Opus Pass-2 of a brief-wiring
PRD): the spec added a "preflight: fetch one cheap item through the Starlink lane, if non-200 fall back
to direct" guard before a Reddit-RSS gather. But Reddit's limit is **≈1 fetch per rolling window per
egress IP** — so the preflight fetch + the real gather fetch on the *same* IP are TWO fetches in one
window → the second is the 429 the preflight was trying to avoid. The "safety check" manufactures the
outage on exactly the constrained resource it guards.

**The durable rule:** when a resource is rate/budget-limited *per the same key the real op uses*
(per-IP quota, per-token quota, per-account API credit, a one-shot lock), do NOT add a separate
preflight probe against that same key. Instead **make the first real operation itself the health
signal** — keep its result if it succeeds, mark the resource down on its failure, and let the op's own
bounded-retry + graceful-degrade handle it. A separate probe is only safe when it hits a *different*
key/endpoint than the real op (a different cheap URL, a status endpoint, a different IP) or when the
probe result IS reused as the first unit of real work (fold probe into fetch, don't spend twice).

This is the budget-aware cousin of the "port-open ping ≠ the thing works" proxy-signal trap: a ping is
a *lying* signal; a real preflight fetch is an *honest* signal that **costs budget**. Both fail — the
ping by under-testing, the preflight by self-sabotage. The fix for both is the same: the first real
operation is the only trustworthy, free health signal.

## Honoring a no-new-dependency invariant when the native client can't (dep-free curl transport)
When a build carries a hard "no new runtime dependency" invariant but the runtime's native client can't
do what's needed (Node's built-in `fetch` can't do SOCKS without an npm proxy package), **shell out to a
CLI that already exists** instead of adding the dep. Pattern (2026-06-14, Reddit gatherer egress lanes):
a `curlFetch(proxyUrl)` transport returns a `FetchResponse`-shaped object by running
`curl -s -S --max-time N --socks5-hostname host:port -A <UA> -w '\n%{http_code}' <url>`, splitting the
trailing status code off the body. Native `fetch` for the direct path, curl transport for the proxied
path, behind one `FetchLike` interface so the rest of the code (and the injected-fetchImpl test seam) is
unchanged. Verify the no-dep claim at closeout with an empty `git diff package.json` dependencies block.
Caveat: a `-w`-appended status code can't surface response *headers* — if the code needs them (e.g.
`Retry-After`), the curl transport returns `headers.get() => null` and the caller must fall back to its
backoff path, which is fine for a best-effort source.

## A periodic "safety net / refresh" reset that fires on an INCOMPLETE pass silently defeats itself (2026-06-15, solo diff-review B1)
A build that adds a **periodic full pass to recover what an optimization skips** (a weekly full-walk
behind a daily early-stop; a periodic full-reindex behind incremental indexing; a full-scan behind a
delta-sync) must reset its cadence clock **only when the pass actually COMPLETED**, never merely when
it "ran without erroring." The trap: the pass is itself bounded (a `maxPages` ceiling, a time budget, a
row cap), so on a heavy/deep input it hits the bound and returns normally — *no error* — having NOT
reached the end. If you stamp `lastFullPassAt = now` on "didn't error," you reset the cadence on an
**incomplete recovery**, so the gap the safety net exists to close stays open AND the net won't retry
for another full interval. The safety net is silently defeated exactly when it was needed most (the
deep/heavy case is the only one that ever needed a full pass).

Real catch (siftly incremental-ingest early-stop): the daily incremental stops after K known tweets;
a weekly full-walk recovers below-frontier gaps. The original wiring stamped `lastFullWalkAt = now`
when `!creditsDepleted && !interrupted` — but a source with >`maxPages` of unknown history hits the
ceiling and returns cleanly, so it stamped a walk that never reached the frontier. A full green unit
suite + an approved 2-pass spec missed it; only the integrated diff-review caught it.

**The durable rule:** gate the cadence-reset on a **completion signal**, not an absence-of-error.
The completion signal is whatever proves the pass reached the end of its input: `nextCursor === null`
(pagination exhausted), `rowsRemaining === 0`, `reachedTail === true` — NOT `exitCode === 0`. And gate
it **per-unit** when the pass is per-unit (per-source, per-shard, per-partition): a source that
exhausted gets stamped; a source that ceiling-capped keeps its old (stale) timestamp so the next run
still treats it as due. This per-unit-exhaustion stamping also resolves the common "fleet-wide vs
per-unit cadence" tension for free — decide conservatively (any unit stale ⇒ run the pass), stamp
strictly (only the units that finished).

**How to hunt it (add to the diff-review prompt):** for any code that writes a "last successful X at"
timestamp/cursor/watermark, ask "what does 'successful' mean here — *ran* or *finished*? And is the pass
bounded such that it can return cleanly without finishing?" If yes to bounded, the reset MUST check the
exhaustion signal, not the error flag. **Regression test:** a bounded pass that hits the ceiling
(`nextCursor` non-null) must NOT advance the watermark; an exhausted pass (`nextCursor === null`) must.
RED-prove by reverting the exhaustion filter to "stamp on no-error" and watching the ceiling-capped test
fail. (Same family as the staleness-watchdog "liveness keyed off *woke up* not *succeeded*" bug above —
both are "treated a partial/awake signal as a completion signal.")

## A posture/recovery state-machine that infers "recovered" from a finding DISAPPEARING will announce a FALSE all-clear when the finding was removed administratively, not fixed (2026-06-15, solo diff-review F1)

This is the single most dangerous bug class for an **alert/watcher recovery path**, and it's a sibling
of the "recovery announced for a job broken right now" bug above — but subtler, because the green tests
all pass and the happy path is correct. The pattern: a posture-delta computes recoveries as *"a finding
key present last tick, absent this tick → emit ✅ recovered."* That inference is only valid when the
finding disappeared because **the underlying condition cleared**. It is INVALID — and inverts a live
break into a false all-clear — when the finding disappeared because the **monitored entity was removed**:
retired, disabled, deleted, deregistered, un-wrapped, filtered out, or aged out of the active set.

Real catch (cron-observer orphan-reconcile): a new reconcile pass auto-`retire`d jobs disabled/removed
from `jobs.json`. A job that was **actively FAILing/STALE when it got disabled** got retired → its finding
vanished from `active_jobs` (the detector only iterates non-retired rows) → the posture-delta read the
key's absence as a recovery → emitted **"✅ <job> recovered (FAIL cleared)"**. The job did NOT recover; it
was administratively removed *while broken*. This is the exact alert-inversion (a 🔴 laundered into a ✅,
a false all-clear over a live failure) the system exists to prevent — and it's literally the symptom
class the user opened the session reporting (a confusing "✅ recovered" alert). 14 green author-written
tests missed it because **every one tested the happy reconcile (an orphan that wasn't paging)**; none
tested *retiring a job that is actively failing right now*. That missing test class is the precise
contract gap a solo author is blind to (same model wrote code + tests: "retire = gone = recovered").

**The durable rule:** a recovery/all-clear emission must be gated on the entity being **healthy NOW**, not
merely on its finding being **absent NOW** — and "absent because retired/disabled/deleted" is NOT healthy.
On the recovery path, look up the entity's live status; if it was administratively removed, **suppress the
✅** and instead emit a distinct, quiet administrative note ("🚫 retired (was FAIL) — no longer monitored",
low severity → a log channel, never the alert channel). Retirement/removal ≠ recovery; deletion ≠ fixed;
filtered-out ≠ resolved. Three audit questions for any recovery/clear/resolve emission:
1. **Why did the finding disappear?** Enumerate every reason a finding key can leave the active set —
   condition cleared (real recovery), entity removed (retire/disable/delete), input filtered, TTL/window
   aged out, an upstream guard now `continue`s past it. Only the *first* is a recovery.
2. **Does the emitter distinguish them?** If recovery is computed purely as set-difference
   (`last_active - now_active`), it does NOT — it announces ✅ for every removal reason. Add a live-status
   lookup.
3. **What reaches the user vs the log?** A real recovery → the alert channel (it closes a loop they saw
   break). An administrative removal → a quiet log note or silence. Never a ✅ to the alerts channel for a removal.

**Operational cleanup the fix implies:** if the buggy emitter already QUEUED false recoveries before you
shipped the fix (a batch/flush queue, an outbox), they still deliver post-fix — scan the pending queue
for the false ✅ rows and expire/drop them so the user never sees them. (Here: 10 pending
"<retired-job> recovered" rows marked expired before flush; the observer's stale removal counters pruned.)

**Regression test (RED-prove it):** drive the REAL state machine end-to-end — entity pages a finding on
tick N, gets removed/disabled on tick N+1 → assert **zero ✅ recovery** and exactly one administrative
note; revert the live-status lookup and watch the test fail (it emits the false ✅). Test the FAIL case
specifically, not just STALE — a retired-while-failing job is the worst instance because FAIL is the
finding a user most needs to not be told is "cleared."

**Two adjacent guards the same review surfaced (reconcile/removal sweeps in general):**
- **A "don't sweep on empty input" guard that checks the raw collection, not the EFFECTIVE set, is
  bypassable.** A reconcile guarded by `if jobs:` (the list is non-empty) still mass-removes everything
  when the list is non-empty but **all-disabled/all-filtered** (effective set empty). Guard on the
  *effective* set (`if enabled_ids:`), and add a **fraction cap** — refuse to remove more than N% of the
  active population in one pass (a bulk-disable / broken-writer / corrupt-source guard), let it recur
  instead. RED-prove with an all-disabled (non-empty) input → 0 removed.
- **A removal that silences a live failure needs a debounce + an operator-visible warning.** Per-tick
  removal should debounce (require the entity absent for ≥2 consecutive ticks before retiring) so a single
  transient source hiccup can't retire a live job. A one-shot operator backfill that bypasses the debounce
  must **annotate** which removal candidates carry an open FAIL/STALE ("⚠️ will be SILENCED") and refuse
  to remove them without an explicit `--force` — so the operator never blind-silences a live failure during
  a bulk cleanup.

## Mechanics that worked (reuse)
- Build the evidence pack by concatenating the actual built files (`for f in …; do echo "=== $f ==="; cat "$f"; done > /tmp/pack.txt`)
  and tell the reviewer "this is the integrated code, ground truth; review it as SHIPPED CODE."
  (See the redaction-safe-pack rule above — a masked secret line in the pack triggers false BLOCKs.)
- Run via `prd-review-pipeline`'s `scripts/opus-review-direct.py` (model-hardcoded Opus, registry
  cycle). Same `hermes -z` / background-poll buffering discipline as a spec review.
- Add a regression test for each real finding, named for the behavior, RED-proven. The ND-1 test
  had to construct the re-break via *real elapsed time* (fresh run, then grace elapses again), not
  a jobs.json rewind — the impossible-scenario trap above.
- **A single `./verify.sh` gate** (lint strict whole-tree + unit + the adversarial dogfood battery,
  exits non-zero on any failure) is the durable artifact — it makes the dogfood probes a permanent
  regression asset, not a one-session script. Scope lint to the whole tree and fix the legacy
  warnings rather than carrying a fragile baseline-count, when the tree is small enough.

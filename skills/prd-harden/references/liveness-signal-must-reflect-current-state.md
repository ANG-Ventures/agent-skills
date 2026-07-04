# A watcher's liveness signal must reflect CURRENT state, not a once-set artifact (the flock-mtime false-wedge class, 2026-06-29)

Sibling to `post-build-diff-review-solo-builds.md` §"liveness keyed off *woke up* not *succeeded*" and
§"a periodic reset that fires on an INCOMPLETE pass." Same root error, a third instance: a watcher reads
a **proxy that does not update when the thing it watches changes**, so it reports a fixed/derived value as
if it were live state. These are the most insidious watcher bugs because the proxy *looks* like a real
signal and the happy path is correct.

## The bug (flock file-mtime as a proxy for lock-hold-duration)
A UDM RA-logger wedge-watchdog read `stat -c %Y <lockfile>` (the lock FILE's mtime) and computed
`now - lock_mtime` as "how long the flock has been held," paging WEDGED past a threshold. **`flock` never
updates the lock file's mtime while the lock is held** — the file is created ONCE (first run / reboot) and
the lock lives on the *file descriptor*, not the file's metadata. So `now - lock_mtime` was just wall-clock
since the file was created → a 5-hour-old lockfile read as "a flock held 5 hours" → a guaranteed false
WEDGED storm, flapping red/green in the logs channel as the SSH/timing jitter crossed the threshold. The logger itself
was 100% healthy (events log advancing every 60s).

**The tell:** a watcher pages on a *duration/age* derived from a file/record timestamp, AND the underlying
mechanism it claims to measure (a held lock, an open connection, an in-flight job) does NOT touch that
timestamp during its lifetime. Ask: "does the thing I'm measuring actually *write* this field while it's in
the state I'm inferring?" For a `flock` lockfile the answer is no — mtime ≠ hold duration. Same trap shape:
inferring "process alive" from a PID file's mtime, "connection open" from a socket-file's ctime, "job
running" from a stamp written only at *start*.

## The two WRONG fixes (and why)
- **Delete the check entirely (the lazy "fix").** This stops the false alarm but loses the capability —
  a genuinely-stuck run now only surfaces ~15 min later via the *other* (events-staleness) signal, with no
  fast/direct wedge detection. A reviewer/user who asked to "fix the false alarm" usually wants the
  detection *restored correctly*, not amputated. (Here an automated agent had already shipped the delete;
  the user explicitly asked to restore real detection instead.)
- **Tune the threshold.** Raising the age limit just delays the false fire; it never goes away because the
  signal is structurally wrong, not mis-calibrated.

## The RIGHT fix: probe the LIVE state directly, then debounce
Replace the stale-proxy read with a probe that tests the **current** condition:
- **Held-now probe:** `flock -n <lock> -c true && echo FREE || echo HELD` over the existing SSH hop. If WE
  can grab it non-blocking → nothing is wedged (FREE); if `flock -n` fails → a run holds it right now
  (HELD). `|| echo HELD` turns the non-zero exit into a *token* so a held lock is never confused with an
  SSH/transport error. `fuser <lock>` is the local equivalent ("is any process holding it").
- **Debounce, because a single live-HELD is NORMAL.** The legitimate run holds the lock for its real work
  (~1s here), so one probe landing mid-run will read HELD without anything being wrong. Only alarm after
  **N consecutive HELD probes**, persisted in a tiny state file (`{"consecutive_held": N}`, atomic
  `os.replace` temp-write, best-effort — a state write failure must NOT crash the check). Size N to the
  watchdog's own cadence: at a 300s launchd interval, `N=3` ≈ 15 min of *continuous* hold before paging —
  match it to the sibling staleness window so both signals agree on "how stuck is stuck."
- **A FREE or UNKNOWN reading RESETS the streak.** Only a *continuous* hold accrues. An unparseable/missing
  probe line (SSH hiccup) → `None` → treated as not-a-wedge, streak reset; an ambiguous probe never pages.
  This is the fail-safe direction for a watcher: ambiguity → don't cry wolf, the next clean probe decides.

Keep the now-unused stale field on the data struct for back-compat (and the now-no-op threshold kwarg with
a `# deprecated no-op` comment) so existing callers/tests don't break — but make the docstring say loudly
that it is NOT used to decide.

## Tests that actually prove it (RED-provable, hermetic)
- `single held probe → no page` (debounce floor).
- `N consecutive held → page on the Nth only` (drive the real `check_and_alert` N times against the SAME
  injected state-file path; assert the first N-1 return None and only the Nth fires).
- `FREE resets the streak` (held, held, free, held → no page).
- `UNKNOWN resets the streak` (held, unknown → no page).
- **Mutation proof the debounce is load-bearing:** `wedge_consecutive=1` makes a single held probe page —
  if it doesn't, the threshold is decorative.
- **Regression guard for the original bug:** a long stale *mtime* + a FREE live-probe + a fresh primary
  signal → NO page (proves the mtime is no longer a wedge input).
- **Hermetic isolation:** every test passes its OWN temp `state_path` (`tempfile.mkdtemp` + a unique file
  per case) so the debounce counter never touches the real one — same discipline as
  `hermetic-test-isolation-side-effecting-functions.md`.

## The LIVE e2e is the only proof that matters (don't ship on unit-green alone)
Unit tests mock the injected probe, so they prove the *debounce logic*, NOT that the real `flock -n` over
SSH actually reads HELD/FREE correctly. Stage the real wedge:
1. Hold the lock for real on the target box in a **background** session (`flock <lock> -c "sleep 40"` as a
   genuinely-backgrounded process — a `&` inside a one-shot SSH session exits immediately and releases the
   lock, so it must be a real long-lived background process holding the SSH session open).
2. Run the REAL probe N times against it → assert it reads `held=True`, debounces, and pages WEDGED on the
   Nth.
3. Release → run once more → assert `FREE` → recovered → streak reset.
This drove the real integration seam (real SSH, real held flock) end-to-end; the unit suite alone would
have shipped a probe whose *parsing* of the third SSH line could have been wrong and never caught it.

## Generalize: the "is X *currently* true?" probe beats every derived-age proxy
For any "has X been stuck/held/open/running too long?" watcher, prefer a **direct current-state probe**
(can I acquire the lock? is the connection answering? is the PID alive *and* doing work?) over a
**duration derived from a timestamp** — unless you can prove the timestamp is written *continuously while X
is in that state*. Then debounce the direct probe (single positive = maybe-transient) and fail safe on
ambiguity. A derived age is only trustworthy when its source advances throughout the watched condition's
lifetime (e.g. an events/heartbeat log the job appends to every tick — that one IS a valid liveness
signal, which is why it stayed as the *primary* check here).

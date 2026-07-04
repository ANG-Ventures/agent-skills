---
name: systematic-debugging
description: "The fleet MASTER debug skill — 4-phase root-cause method (understand before fixing) + when to delegate an ephemeral debug subagent."
version: 1.2.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation, master-debug]
    related_skills: [test-driven-development, prd-harden, prd-plan, subagent-driven-development, qa]
---

# Systematic Debugging — the fleet's MASTER debug skill

> **This is the canonical "master debug" skill** (alias: master-debug). Other skills — `prd-harden`,
> `qa`, `test-driven-development` — point here for the root-cause method. The skill keeps its name
> (`systematic-debugging`) so the ~19 references and existing routing tables don't break; "master debug"
> is positioning, not a rename. Load it for ANY technical bug: test failure, prod incident, unexpected
> behavior, perf problem, build/integration failure, or a model behaving wrong.

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## Reference map (4 tiers — load on demand, zero prompt cost until used)

The spine below is the always-loaded method. Domain walkthroughs and worked examples live in
`references/*.md` — load the one that matches your situation:

| Tier | When | References |
|---|---|---|
| **general-method** | the core loop, escalation, minimization | `read-prior-investigation-before-fixing.md` · `bisection-and-delta-debugging.md` (bisect + delta-debug + the hypothesis-log) |
| **instrumentation** | "observe before theorizing"; the model/binary/effect is the symptom; a fan-out pipeline isn't progressing | `instrument-before-guessing-when-model-is-symptom.md` · `log-effect-not-lifecycle.md` · `prove-wire-call-with-tls-mitm.md` · `per-path-probe-aggregate-failure-and-representative-input.md` (multi-lane/replica/backend: probe EACH path with a REAL workload item; an aggregate "all blocked" + a generic probe both lie) |
| **verification of a fix** | you fixed a real bug but the live symptom persists; you keep saying "fixed" and it isn't; you edited code while a daemon was running | `multi-layer-fix-and-stale-process-traps.md` (process holds code imported AT START — edit-after-launch runs OLD code; one symptom can have N stacked root causes; "fixed" is earned only when the user-visible completion signal moves on the REAL path; grep for OTHER call sites of the same fragile op before claiming done) |
| **agent** | LLM/agent-specific traps (handed-off diagnosis, miscounts, self-transforming systems) | `verify-handed-off-diagnosis-against-logs.md` · `classify-on-full-evidence-not-first-keyword.md` · `count-gap-and-enriched-not-indexed.md` · `stale-count-and-current-state-attribution.md` (a log COUNT is silent about WHEN; check timestamps + current authoritative state, e.g. permissions, before blaming an actor) · `self-transforming-systems-debugging.md` · `adversarial-gauntlet-for-wire-transform-sidecars.md` |
| **harness/scoring** | a metric reads 0/N or all-fail; a per-trial field holds a stringified error; an `except Exception` scores structural failures as data; subprocess fails but in-process passes | `swallowed-error-as-fake-fail-force-the-traceback.md` (force the real traceback before theorizing; a broad except is a fake-FAIL factory; uniform 0/N points at the rig not the system; interpreter/venv guard) |

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase 0: Read the Prior Investigation (repos with history)

**BEFORE Phase 1, in any repo that has existing specs/docs:** the "obvious next fix"
you'd derive from raw forensics/logs is often **already shipped or deliberately
declined** by prior sessions. Find the status board (`the AGENTS doc`, `SPEC-*-CONSOLIDATED.md`,
fix-status table) and read it as source of truth before proposing anything; `grep src/`
for the mechanism before assuming it's unbuilt; and confirm what's actually RUNNING
(daemon start time vs file mtime — stale long-running processes silently run old code).
A data-gated fix can be **MEASURED → DECLINED** (a valid outcome, not a failure). When
you spot the duplication trap or a missing status board, leave an anti-duplication
artifact (the AGENTS doc + status table) so the next agent doesn't repeat it. Full playbook,
the Fix B measure-then-decline example, and the worktree subagent boundary:
`references/read-prior-investigation-before-fixing.md`.

**Forward-work variant — verify a "pending" feature isn't ALREADY LIVE before you build for it.**
Phase 0 isn't only for fixes. Before you build a watchdog, write a gate-tracker, schedule a
"cutover," or perform a "flip" that docs/handoffs call *pending/shadow-only/not-yet-wired*, prove
it against the running system — a stale status line is a hypothesis, not live truth. Run the
three-check triad: (1) **call-graph reachability** (does the "shadow"/pending code sit on the live
path? — a function NAMED `*_shadow` or a commit labeled "shadow-only" can be the live authority;
trace it, don't trust the name), (2) **`git merge-base --is-ancestor <sha> HEAD`** on a clean tree
the process runs from, (3) **byte-match re-run on real data** (the would-be output equals what
actually shipped → already live). A real 2026-06 session built a whole coercion-streak watchdog —
and nearly did a live Hard-Config edit to two production briefs — for a cutover that had landed a
week earlier. Includes the cleanup obligation (correct the stale doc, PAUSE-don't-delete the moot
watchdog and close the tracker moot) and the true gate-cross measurement for flips that ARE pending:
`references/verify-feature-already-live-before-building.md`.

**Close-out variant — a "WONTFIX / terminal / unrecoverable / can't / gone" verdict is itself a
HYPOTHESIS, ground-truth it before you ship it.** The easy close-out dispositions ("the data is gone,"
"this is terminal," "too risky → BACKLOG") feel like honest floors but are usually *assumptions about
the world* you made without checking — and a probing user will overturn them. Before writing one: (1)
**check disk** for the data you think you'd have to re-fetch (saved captures, dumps, prior-run/`/tmp`
artifacts often already hold it); (2) **re-derive the root cause on the real records** — the flag's
*reason string* is a symptom, and one label ("reconcile_fail," "no_match") can hide N distinct fixable
causes; (3) **scope the real blast radius** and do the small safe slice instead of deferring the class.
Only "I measured it and it's genuinely impossible" (state the number) is a real WONTFIX — "I assumed
it's impossible" is not. Real session: 2 of 3 closeout WONTFIX/BACKLOG calls were wrong (a 98%-coverage
capture was still on disk; "terminal" reconcile-fails were two systematic transform bugs → 9/12
recovered). The "missing beats wrong" gate makes the downside of *trying* near-zero, so a false WONTFIX
leaves real recoverable value on the floor for nothing: `references/wontfix-terminal-is-a-hypothesis-ground-truth-it.md`.

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes
- **The errno often IS the diagnosis.** macOS-specific: a file READ that fails with `Resource deadlock avoided` / `EDEADLK` (`os error 11` / `[Errno 11]`) — or `read_file` returning EMPTY despite a non-zero `ls` size — under `~/Documents`/`~/Desktop` is almost always an **iCloud-evicted dataless placeholder**, NOT a permission/tool/code bug. Confirm with `stat -f "%N flags=%Sf"` (look for the `dataless` flag), fix with `brctl download <file>`, then read (via `cat`/`open()`, not `read_file`, whose dedup cache poisons itself). Full recipe + pitfalls: `references/macos-icloud-dataless-file-read-deadlock.md`.
- **Classify on the FULL message, not the first matching keyword.** When bucketing many failures by a substring, read a representative sample of the *complete* strings first — a word like "unavailable" can appear inside a recoverable rate-limit error. When labeling failures transient-vs-terminal, transient/recoverable wins ties (mislabeling transient as terminal abandons recoverable work). And a subagent/batch `completed` status is not proof of work — verify `tool_trace`/output/row-counts. Worked examples + the "check the skill's documented pitfalls before inventing a novel cause" rule: `references/classify-on-full-evidence-not-first-keyword.md`.

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Use the `terminal` tool to run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 3b. Bisect to the exact change (when "what changed" is a range, not a line)

When the regression lives somewhere in a range of commits / a large changed surface and reading the
diff won't pinpoint it, **bisect — binary-search the change instead of guessing.** This is a named
Phase-1 step, not a fallback:

- **`git bisect`** when you have a known-good and known-bad commit and a deterministic reproduction:
  ```bash
  git bisect start; git bisect bad; git bisect good <last-known-good-sha>
  git bisect run ./repro.sh    # repro.sh exits 0 on good, non-0 on bad → lands the first bad commit
  git bisect reset
  ```
- **Delta-debugging / input minimization** when the *input* (not the code) is what's large: shrink the
  failing input by halves, keeping it failing, until you have the **minimal reproduction** — the
  smallest input that still triggers the bug. A 3-line repro beats a 3000-line one for finding the cause.
- **Keep a hypothesis-log** during any multi-round investigation so you don't lose state across
  compaction or re-test the same dead end: one line per round — `hypothesis → test → result → next`.
  It's the audit trail that makes the Rule of Three (Phase 4) actually countable.

Full mechanics (automated `git bisect run`, the ddmin delta-debug loop, the hypothesis-log template):
`references/bisection-and-delta-debugging.md`.

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

**Special case: LLM-in-the-loop systems.** When the symptom is "the model behaved unexpectedly" (invalid tool call, refused, hallucinated, wrong format after a config change), source-code reasoning misleads worst. The model is not reading your source code — it is responding to whatever bytes actually reached the model API. Reasoning about which transform fired is a hypothesis, not a finding, until you see the bytes.

**Mandatory sub-step for LLM systems:** capture the exact request bytes the model received and the exact response bytes it returned before forming a root-cause hypothesis. ~50 lines of opt-in body-capture instrumentation can resolve in minutes what days of source-code reasoning miss. See `references/instrument-before-guessing-when-model-is-symptom.md` for the minimum useful capture pattern, a real-world example (2026-05-12), and anti-patterns this prevents.

**The instrumentation outlasts the bug.** Once you've built byte-capture for one investigation, gate it behind a config flag and leave it in. The next diagnostic question in the same system gets answered in minutes instead of rebuilt from scratch. In the 2026-05-12 case, the same `captureBodies` feature later revealed a second class of bug (casing-collision in a transform whose test suite only used homogeneous lowercase fixtures) — without it, that bug would have shipped to production for the same reason the first one did.

**When the binary is proprietary and the question is "what exact request does it make?"** (auth, headers, scope, endpoint — e.g. "is calling this undocumented endpoint allowed / are our reimplemented headers right?"), terminate its TLS and read the decrypted request rather than reasoning about its source. Escalation ladder: plain logging proxy → CONNECT-logger (names the real host when the binary ignores `*_BASE_URL`) → TLS-MITM with your own CA trusted via the runtime's CA env. Then route YOUR client through the same MITM and diff. Watch for the chat redaction layer rewriting identifier tokens in your output — trust the raw log bytes. Shred the CA private key after. Full recipe (openssl CA, Python stdlib MITM, tmux TUI-driving, the redaction-rewrite trap): `references/prove-wire-call-with-tls-mitm.md`.

For "ran cleanly, did nothing" bugs — injected DOM scripts, MutationObservers, middleware, event listeners, intercepted fetch handlers where lifecycle telemetry (`attached`, `registered`, `subscribed`) looks healthy but the user-visible symptom persists — read `references/log-effect-not-lifecycle.md`. It captures the failure pattern, a 2026-05-14 HA-sidebar worked example (~90 minutes lost to wrong diagnostic because `[ScriptName] observer attached` was treated as proof of correctness), the minimum-useful-logs template (candidates / matched / mutated counts), and the class invariant: **telemetry at the layer of effect, not the layer of installation.**

**Display/GPU/Wayland black-screen, refresh, VRR/G-SYNC/DRR, HDR, or DP→HDMI-adapter bugs** (machine reachable over SSH/RDP but the monitor misbehaves): do **read-only probes before changing settings**, and isolate at 4K60 SDR before adding HDR/VRR/high-refresh. Load the matching **domain-tier** reference from the map above (`windows-display-*`, `*-dp-hdmi-adapter-*`, `displayport-hdmi-vrr-adapters`, `ubuntu-gnome-wayland-display-audio-debugging` + its `scripts/ubuntu-wayland-display-summary.py`). Common rule across all of them: high *fixed* refresh support ≠ VRR exposure; adapter firmware/rollback and RGB-Full-vs-Limited are the usual culprits — don't blame the GPU first.

### 4b. Re-derive a Handed-Off Diagnosis Before Patching

**WHEN you're given someone else's root-cause writeup (another agent, a teammate,
a past session, or your own earlier reasoning) plus an approved fix and asked to
"just implement it":** the diagnosis is a HYPOTHESIS, not a finding. Re-derive it
from the primary evidence (the actual logs/metrics it was built from) before
touching code. Grep the timestamp window yourself, match the failure signal
(error type, timing gaps, token counts) to the claimed mechanism, read the code
paths the fix would touch, and check for documented prior rationale on any
threshold you'd change. If the mechanism turns out wrong, STOP and re-present —
even when the fix was already approved, because approval was granted against the
wrong model of the bug. Worked example (Hermes Codex non-streaming hang: TTFB was
*not* streaming-only; it just lost a race to a shorter 90s stale timer) and the
full 5-step procedure: `references/verify-handed-off-diagnosis-against-logs.md`.

### 5. Static-site URL/path-dependent asset bugs

**WHEN a static page works at `/route` but breaks at `/route/` (or only under nested paths):** treat asset resolution as the data flow. Reproduce both URL shapes, inspect the returned HTML, and verify the browser-resolved resource URLs — not just that the page returns 200. Relative asset references like `src="logo.png"` or `url('bg.jpg')` resolve differently under `/route/` (`/route/logo.png`) and can be masked by catch-all/fallback routing that returns HTML with status 200 instead of the image.

Minimum evidence before fixing:
- Fetch both page URLs and compare asset references in the HTML/CSS.
- Fetch the resolved asset URLs from the broken path and verify `Content-Type` plus binary signature/size; a 200 `text/html` fallback is still a broken image.
- Use browser/resource inspection when available to confirm the actual loaded `img`, CSS background, and favicon URLs.

Preferred fix:
- Make site-root assets root-relative (`/logo.png`, `/bg.jpg`, `/favicon.svg`) or absolute, then redeploy.
- Verify both `/route` and `/route/`, plus direct asset endpoints and favicon endpoints.

### 5b. A count is not a diagnosis; an enriched field is not an indexed field

**WHEN a batch job reports `attempted=N succeeded=M` (M<N) and you're about to attribute the
gap to a failure cause** ("the missing items are expired/unreachable/errored"): STOP and
confirm what the counters actually mean before asserting. The "succeeded" counter often ticks
only on a *positive result*, not on *absence of error* — so the gap can be benign empty
results, not failures. If the loop has no per-item `try/catch` and the run completed, then
*nothing errored* (a real error would have aborted the whole run). Read the loop, pull a few
gap items from the DB, and probe one live before claiming a cause. Re-running non-failures
wastes spend and yields the identical result.

**WHEN you add a derived/enrichment field and assume it's searchable:** trace it to EVERY
consumer, not just the obvious one. Hybrid-search systems have independent text-assembly paths
(FTS/keyword builder, embedding-input builder, export/render, ranker); a field written but read
by only a subset is a silently half-wired feature (e.g. media text in FTS but never in the
vector index). Prove the fix behaviorally with a query whose only possible match is the new
field. Both traps + the cheap checks + the behavioral proof: `references/count-gap-and-enriched-not-indexed.md`.

### 5c. A cycling/transient state defeats a "held for > N seconds" detector — sample the STEADY signal, not the instantaneous state

**WHEN you're building a detector/watchdog/health-check whose condition is a state held over time** ("if X has been in state S for > N seconds → act"): first confirm the failing system actually *sustains* that state. A surprising number of stuck/wedged systems **cycle rapidly between two states** (`S → idle → S → idle …` every few seconds) instead of holding one — so the instantaneous state you sample is sometimes S and sometimes the other phase, and a "held in S for > N s" gate **silently misses the very failure it was written to catch** (every sample reads a short in-state duration and classifies it OK). This bit a real watchdog (2026-06-12): the spec assumed a satellite stuck in `listening` would *hold* `listening`, but the real wedge cycled `listening↔idle` every ~15.8s, so the spec-derived `state==listening for >90s` gate would have completely missed it.

The fix is to **key the detector on a steady/aggregate signal that the cycle *produces continuously*, not on the transient state itself.** In that case the reliable discriminator was the *cadence* of empty STT runs in the logs (≥3 `transcript='' audio_s=15.00` in 60s) — present on every loop iteration regardless of which phase you sampled — with the instantaneous state used only as a coarse sanity check, never the gate. General rule: a duration-of-state condition is only valid if you've **empirically confirmed the state is monotonically held, not flapping** — pull two state reads a few seconds apart (or `journalctl`/log over a window) and look for cycling before you trust "it's been in S for a while." And critically: this is exactly the class of detection bug that **unit tests written from the same wrong spec will ALL pass** — only a live run against the real flapping system exposes it (instrument before trusting the spec's state model; the live test caught 3 such bugs the green unit suite couldn't).

### 5d. A bursty long-running job is NOT wedged just because an instantaneous sample reads idle — measure the STEADY-STATE rate over a window before you kill it

**WHEN a long-running, throughput-style job (batch ingest, crawler, transcription
pipeline, queue drainer) looks stalled** — `0% CPU`, no active child procs, a
progress counter that hasn't moved in your last few snapshots — STOP before you
restart/kill it. Throughput jobs are **bursty by construction**: politeness sleeps,
per-item rate limits, slow remote steps (a ~7s JS-challenge solve, a remote ASR
round-trip), and acquire-ahead buffering mean that at any given *instant* most
workers are sleeping and local CPU reads ~0. An instantaneous `ps`/`%CPU`/one-shot
counter read catches the trough and lies. This bit a real session (2026-06-12): a
healthy YouTube-transcription ingest that had climbed 3,335→4,989 overnight was
misread as "wedged" from a string of 0%-CPU / flat-count snapshots, and got
**SIGKILL-thrashed ~8 times** chasing a phantom — every kill (rc=137/143) then
*became* the flat-count evidence that "confirmed" the wedge. Classic self-inflicted
feedback loop.

**Before concluding a long-running job is stuck:**
- **Measure the rate over a real window, not a point.** Sample the durable progress
  signal (manifest done-count, rows committed, files written) at `t=0` and again
  after a window sized to the job's *known* cadence — if the historical rate is
  ~110/hr (~1.8/min), a 2–4 min "+0" proves nothing; you need 5–15 min. Read the
  job's own historical tick deltas (its log) to learn the expected rate first.
- **Watch a churning signal across several samples,** not one: a staging-dir count,
  child-proc count, or active-connection count taken 3× over 30–60s. `2→0→3` is
  *alive and cycling*, not dead. One `0` is just the trough.
- **Distinguish "parked on a lock" (real wedge) from "sleeping on a rate limiter"
  (normal).** `sample <pid>` (macOS) / `py-spy dump` / `/proc/<pid>/stack`: workers
  in `time_sleep`/`nanosleep` are throttled-and-fine; the main thread on
  `acquire_lock` *with no worker ever progressing across a full window* is the wedge.
  The stack alone isn't enough — pair it with the windowed rate measurement.
- **A frozen secondary artifact may be stale, not live.** A telemetry/log file with
  an old mtime can read like "nothing's happening since 08:51" when it's simply not
  the file the current run writes. Check mtime and whether THIS process owns it
  before treating its contents as live evidence.
- **Verify each component in isolation before blaming orchestration.** Downloads
  land fine (run one by hand), all backends respond fine (curl the real endpoint
  with a real input), upstream passes a health probe — if every piece works
  standalone, "it's all broken" is wrong; you're misreading the aggregate.
- **"Bytes moving" is NOT "work completing" — pick the COMPLETION signal, not an
  intermediate one.** A staging dir whose size grows (`du -sh` climbing), child
  procs cycling, and a downstream service that flips to `busy`/`model_loaded=true`
  all feel like progress — but a job that *keeps restarting the same unit of work*
  produces every one of those signals while finishing nothing. The 2026-06-13 trap:
  claimed a cell-only ingest "is downloading" because `.audio-tmp` bytes climbed,
  when the `.part` files were churning (appear → grow → vanish → restart) and ZERO
  completed-and-finalized. The honest progress chain is **completed-input
  (`source.m4a`, not `*.part`) → processing-proc running (`ffmpeg`) → durable output
  count rising (`individual/*.txt`, committed rows, manifest `done`)** — watch the
  LAST link, never the first. And a worker proc whose `etime` exceeds the unit's
  *known* duration (a ~30–90s audio pull still running at 4 min) is a stalled/looping
  unit, not a healthy slow one. Don't tell the user "it's working" off an
  intermediate signal — say "bytes are flowing but nothing has finalized yet" until
  the completion counter actually moves. (Root cause that session: yt-dlp
  `--throttled-rate 100K` aborting legit slow downloads on a ~50–100 KB/s hotspot —
  see `youtube-ingest` ref `mobile-hotspot-egress-lane.md`.)

**And the meta-rule: do not thrash a system the user depends on.** Repeated
`pkill -9` + restart on a *resumable* job is not free — it destroys in-flight work,
resets governors/cooldowns, and manufactures the very flat-progress symptom you're
chasing. If your hypothesis is "wedged," prove it with a windowed measurement FIRST;
if you've already killed it 2+ times and each kill is your only new "evidence," you
are the bug. Restore the last-known-good config, let it run **uninterrupted** for a
window sized to its real cadence, and read the deltas before touching it again.

### 5e. Test fails in a multi-file run but passes in isolation → cross-file leak OR dev-machine env, NOT a code bug

**WHEN a test fails in `pytest <dir>/` but passes as `pytest <dir>/one_file.py`:**
classify it before "fixing" anything — there are three distinct causes and only
one is a product bug:

1. **Cross-file module-state leak.** A module-level cache/dict/singleton (provider
   health cache, client cache, runtime override) gets dirtied by an earlier file
   and survives into a later one because they share one interpreter. Tell: passes
   isolated, fails only after specific earlier files. Fix: reset the cache in the
   hermetic autouse fixture (most have an author-provided `_reset_*()`/`.clear()`
   "for tests" entrypoint already — wire it in, don't write a new one). Fix the
   **whole class** — grep the module for sibling module-level mutables and reset
   all of them.
2. **Dev-machine credential/Keychain/HOME leak.** Test reads a real source the
   hermetic fixture doesn't redirect — macOS Keychain (`security
   find-generic-password`), `~/.claude/.credentials.json` via un-redirected `HOME`,
   `pwd.getpwuid().pw_dir`, an exported `*_REAL_HOME`. Tell: fails **even in
   isolation** on your box, green in CI (Linux, clean HOME). Assertion shows your
   real token/path (`sk-ant-...`, `/Users/you`). Fix: block the source in the
   hermetic fixture — stub at the **layer the leak enters** (e.g. default
   `platform.system → "Linux"` so a Keychain branch early-returns), NOT at a
   function a Keychain-*behaviour* test re-patches (you'll break that test —
   verify the keychain/priority tests stay green after your stub). Add the leaked
   env var to the fixture's strip list.
3. **Accumulating multi-file state with no single polluter.** Fails only in the
   FULL run; no single earlier file (or quarter-bisect chunk) reproduces it. This
   is the expensive one — bisection costs ~Nmin/run. Make the scope call
   explicitly: if it's green under the canonical per-file-subprocess runner (what
   CI/prod use), the cost of hunting can exceed the value. Report it classified
   rather than thrash.

**Pitfall — do NOT `git stash` to verify "does this fail on clean HEAD too?" when a
pre-existing unrelated stash exists.** The instinct, when a test fails in a big run, is
to stash your WIP and re-run on clean HEAD to prove the failure is pre-existing. But
`git stash push <file>` + later `stash pop` can collide with an OLDER stash already on
the stack and leave a merge-conflict on a totally unrelated file (real hit 2026-06-24:
the pop conflicted `FLASH-LOG.md`, nothing to do with the change under test). Cheaper and
safe: copy the file aside (`cp x /tmp/x.bak`), `git checkout HEAD -- x`, run, then restore
the copy — OR use a `git worktree` for the clean-HEAD checkout. Never juggle the stash
stack mid-verification. And first confirm a failure is even YOURS: **re-run the single
failing file in ISOLATION** (`pytest path/to/one_file.py`) — if it passes alone but fails
in the full run, it's cross-file pollution or a known pre-existing fail (per the classes
below), not your change.

**The meta-rule:** the canonical runner (per-file subprocess) hides ALL of class 1
& 3 — so "CI is green" is true and these only bite single-process local runs.
That makes them low-severity but real hermeticity debt. Fix the cheap, well-bounded
ones (1 + the credential half of 2) in the shared fixture; don't scope-creep an
unrelated module's accumulating-state pollution into a focused change — classify
and report it.

**Don't bisect class 3 — instrument it.** Progressive-prefix bisection is O(N)
full-dir runs (~minutes each). Far faster: add a TEMPORARY autouse probe in the
failing test's conftest that, at the failing test's entry, snapshots candidate
module globals + an env-key list and writes them to a tmp log; run the file
ISOLATED (clean baseline) and in the FULL dir, then DIFF the two snapshots. The
leaked state is whatever differs. Then `grep` for who writes it — no bisection.
Real 2026-06-19 hunt found 3 stacked leaks this way in ~4 instrumented runs:
(a) `agent.models_dev._models_dev_cache` poisoned by a test that assigns a tiny
SAMPLE_REGISTRY with no teardown (a sibling test's `_fresh_modules()` reimported
auxiliary_client but NOT models_dev, so the stale cache survived and flipped
vision-capability lookups); (b) `hermes_cli.skin_engine._active_skin` singleton
left on a non-default skin, changing a default-skin tool-prefix assertion;
(c) **bare `*_KEY` credential env vars** (`CLAUDE_API_PROXY_KEY`,
`CLAUDE_API_PROXY_F{N}_KEY`) that `env_loader` seeds into `os.environ` from the
real `the harness secrets file` at IMPORT time (before the test's `HERMES_HOME` redirect),
which the credential-strip filter missed because it only matched `_API_KEY`, not
bare `_KEY` — they registered as providers and hijacked `resolve_provider("auto")`.
Lesson from (c): a credential-strip allowlist keyed on `_API_KEY` silently misses
`_KEY`/`_PROXY_KEY`; widen the suffix set and verify no benign `_KEY` var is
over-stripped (the only one, `HERMES_SESSION_KEY`, was already handled elsewhere).

**Class-3 leak #4 — a CONSUMER module's early-bound symbol, NOT the `sys.modules`
slot (2026-06-22, `tests/gateway/`).** A test that mocks a package by
`sys.modules["telegram"] = mock` + `sys.modules.pop("gateway.platforms.telegram")`
+ re-`import`ing the consumer rebinds the consumer's *module-global*
(`gateway.platforms.telegram.ParseMode = <mock string>`). The mock's
`monkeypatch.setitem`/slot revert does **NOT** un-rebind the consumer — Python
copied the reference into the consumer's `__dict__` at import time. So the leak is
one layer deeper than the slot, and it poisons every later test that reads the
consumer global. Three traps the instrument-first hunt surfaced:
1. **The probe must snapshot the CONSUMER binding** (`gateway.platforms.telegram.ParseMode`),
   not the `sys.modules['telegram']` slot — they diverge, and only the consumer one
   tracks the actual failure.
2. **The fix is in-place re-bind, NOT re-import.** `del sys.modules[consumer]` +
   `import_module` makes a **NEW** module object; already-imported consumers
   (`from X import Adapter` at another test's module top) read the **original**
   `__dict__` (`Adapter.method.__globals__ is old_module.__dict__`). So the
   teardown must mutate the live module's attribute in place
   (`consumer.ParseMode = real_constants.ParseMode`), after restoring the real
   `telegram*` slots first.
3. **The guard must discriminate by REPR/IDENTITY, never `==`.** The leaked value
   was a plain `str` `"MarkdownV2"`; the real symbol is a `StringEnum`
   (`ParseMode.MARKDOWN_V2`, a `str` subclass) whose `.value` IS `"MarkdownV2"`. So
   `parse_mode == "MarkdownV2"` is **True for BOTH** poison and clean — a `==`
   assertion detects nothing AND can't RED-prove the fix. Assert on
   `"MARKDOWN_V2" in repr(x)` (the member-name carrier — true for the real enum and
   the gateway-test MagicMock member, false for the leaked plain string) or
   `x is RealEnum` / `isinstance(x, RealEnum)`. **Any time a mock replaces a
   `StringEnum`/`IntEnum` member with its bare value, `==` is a blind assertion.**

**Honest scope note (D-5):** the canonical order (`-p no:randomly`) is necessary
but NOT sufficient — `-p randomly --randomly-seed=S` exposes MORE leakers the fixed
order hid (the gateway suite had ~25 extra random-order failures in 5 *other* files
after the canonical order was clean). Fix the canonical order as the shippable
strict improvement, then BACKLOG full order-independence as its own campaign; don't
claim "all seeds green" off a canonical-only run.

**Class-3 leak #5 — a test importing a CLI ENTRY-POINT module inherits the
process's `sys.argv`, which under pytest carries plugin flags that the module
mis-parses at import (2026-06-22, `tests/gateway/` random-order).** Under
`-p randomly`, ~14/25 failures were a single root cause: a gateway test does
`from hermes_cli.main import …` inside a test body; `hermes_cli/main.py` runs
`_apply_profile_override()` **at module import** which scans `sys.argv` for a
`-p <profile>` flag — and pytest's own `-p randomly` (the plugin-activation flag)
collides exactly with Hermes's `-p <profile>`, so the import resolves profile
"randomly", fails, and `sys.exit(1)`s. The victim is *seed-dependent* (whoever
imports the CLI module first), the cause *constant*. Three lessons:
1. **Diagnose by error STRING, not by victim.** The failing test varies by seed; a
   `--tb=line | grep -oE "<error-string>" | sort | uniq -c` histogram collapses a
   scary 25-failure spread into "14 × one cause + ~10 × others" in one run — far
   faster than chasing which test failed this seed.
2. **The fix is a session-level argv reset in `pytest_configure`, BLANKET not
   surgical.** `sys.argv[:] = [sys.argv[0]]` (capture-once for xdist re-entrancy,
   restore in `pytest_unconfigure`). Blanket because the collision is general to
   pytest's `-p` (any `-p <plugin>`), not specific to randomly; a value-only token
   strip leaves a dangling `-p` that consumes the next arg. Safe iff no test reads
   the process argv (grep to confirm).
3. **The root product fragility (argv-scan + `sys.exit` AT IMPORT) is a real
   side-effect-at-import anti-pattern** that breaks any embedding (notebook,
   subprocess wrapper), not just pytest — file it as a product backlog (move the
   scan into `main()`), don't call it "correct" and patch only the test.
   Companion class (#4-adjacent): a test that builds an adapter via `object.__new__`
   (bypassing `__init__`) leaves attrs like `self.platform` unset; a `logger.info(
   "[%s]…", self.name)` whose `self.name` reads that attr only EVALUATES the arg
   when the logger is at INFO — so a logging-level leak turns a latent
   missing-attr into an order-dependent `AttributeError`. Fix: set the attr in the
   test helper (mirror `__init__`), don't rely on the log staying disabled.

**Class-3 leak #6 — the random-order campaign: when a config-bridge writes process env via RAW
assignment, snapshot/restore the WHOLE env, don't enumerate the leaked vars (2026-06-22, `tests/gateway/`
`-p randomly`).** After the canonical-order suite is clean (#5's honest D-5 backlog), `-p randomly
--randomly-seed=S` surfaces a fresh wave of order-dependent failures. The 2026-06-22 campaign found the
residual was **5 distinct mechanisms, not the "~4" the honest note guessed** — and the dominant one
(15/16 on seed 1) was a *raw `os.environ[...] =` write*: `load_gateway_config()` bridges `config.yaml`
platform settings into ~44 `*_ALLOWED_*`/`*_MENTION_PATTERNS`/`*_ALLOWED_TOPICS`/… env vars by direct
assignment. **`monkeypatch` does NOT revert a raw `os.environ` write** (it reverts only what *it* set), so
any test that calls the loader leaks those into every later test; a later real adapter reads the leaked
gating var (`TELEGRAM_ALLOWED_TOPICS=8` → a general-topic guest message fails the topic gate;
`SLACK_ALLOWED_CHANNELS` → a mention is dropped before `handle_message`). Lessons, each a reusable rule:
1. **Fix the env class by snapshot/restore of the WHOLE `os.environ`, NOT a strip list.** A
   hand-maintained "vars the bridge writes" list (even one that already exists — the gateway suite had a
   *partial* `_HERMES_BEHAVIORAL_VARS` strip covering 11 of 44) is a SECOND representation of the bridge's
   behavior that re-drifts the moment the bridge adds a var, and a grep-guard that derives the set from
   `config.py` source **fails OPEN** on a loop/`update`/computed-key write (a guard that greens while the
   bug is live is worse than none). The by-construction fix is `snapshot = dict(os.environ)` at an
   autouse fixture's setup and `os.environ.clear(); os.environ.update(snapshot)` at teardown — no list,
   source of truth IS `os.environ`, immune to *how* the write is coded, fails closed. Scope it to the
   subsuite whose evidence you run (a gateway conftest, not root) so blast radius == evidence radius, and
   make it an explicit dependent of the root hermetic fixture so autouse ordering can't invert.
2. **A module-global CLASS rebind leaks a stale identity that `isinstance` can't see (`repr` is
   identical).** `_define_discord_view_classes()` does `global ClarifyChoiceView; class ClarifyChoiceView`
   — re-defining the global to a NEW class object. A test that triggers it makes a consumer's import-time
   binding stale → `isinstance(view, ClarifyChoiceView)` is False with an *identical* repr. Fix BOTH ends:
   (a) a function-scoped leaker-restore fixture (snapshot+restore the globals), AND (b) make the consumer
   read the class via the LIVE module attr (`isinstance(x, mod.ClarifyChoiceView)`) — production builds it
   via a bare-name `__globals__` lookup at call time, so reading it live means consumer and production can
   never disagree (immune to ANY leaker). (b) is the real guarantee; a grep for "other callers of the
   rebind fn" is a best-effort tripwire only (fails open on indirect calls — never the guarantee).
3. **`sys.modules.setdefault("telegram"/"discord", mock)` makes the FIRST file win the slot; a
   plain-string ParseMode mock then poisons the consumer.** Many gateway files install a mock via
   `setdefault` (so the first to run wins) and some set `ParseMode.MARKDOWN_V2 = "MarkdownV2"` (a plain
   `str`). The consumer (`gateway.platforms.telegram`) early-binds `ParseMode`; once poisoned, every later
   `"MARKDOWN_V2" in repr(parse_mode)` assertion fails (`repr("MarkdownV2")` lost the member name — and
   `==` can't detect it: ParseMode is a `str` subclass so `MARKDOWN_V2 == "MarkdownV2"` is True for the
   poison AND the real enum). Two-layer fix: a conftest autouse fixture that (i) snapshots+restores the
   guarded `sys.modules` slots + consumer bindings that CHANGED during a test (identity compare, so
   steady-state mocks are untouched), AND (ii) **normalizes a COLLECTION-TIME poison at setup** — a leaker
   installs its mock at module *import*, before any test setup, so snapshot/restore captures the
   already-poisoned value; detect the poison signature (plain `str` whose repr lost the member name) and
   rebind to a healthy MagicMock whose repr carries the name. **Scope the repair to the POISONED member
   only — do NOT also rebuild/restore its sibling co-members.** `ParseMode` and `ChatType` live on the
   same mock `telegram.constants`, but only `ParseMode` is ever poisoned (the plain-string `MARKDOWN_V2`);
   `ChatType` carries *meaningful* string values (`GROUP="group"`, `PRIVATE="private"`, …) that tests
   compare against directly (`chat_type == "group"`). A first cut that normalized/snapshot-restored BOTH
   replaced `ChatType` with a generic `MagicMock` whose members return arbitrary mocks → broke unrelated
   tests with `assert 'dm' == 'group'`, and **CI caught it (a per-file shard) when the local random-order
   gate did not** (the regression bit CANONICAL order, which the seed sweep doesn't exercise). Lesson: when
   you repair ONE leaked symbol, touch ONLY that symbol; a sibling that *looks* parallel may carry real
   semantic values your blanket fix destroys — and a by-construction test-isolation fix still needs the
   canonical `-p no:randomly` run AND the per-file CI shards re-checked, because a random-order-only gate
   can't see a regression that lands in fixed order.
4. **Other small classes the same sweep found:** a session **contextvar** reset only at *teardown* leaves
   the FIRST test exposed to a leak from an earlier file → reset at setup too; a module-global **lock
   handle** (`gateway.status._gateway_lock_handle`) whose acquire short-circuits when non-None leaks
   against a gone tmp_path → autouse-reset it around each test. And the honest INV-2 residual: a **real-
   time timing test** (`test_stream_sends_keepalive_during_quiet_tool_gap`, a 0.01s SSE keepalive vs a
   0.65s gap) flaked ONCE under full-suite event-loop starvation, passed on re-run of the same seed and
   3/3 in isolation — that's a load flake, NOT order-pollution; don't "fix" a real-time assertion to chase
   a green (you'd mask a real keepalive regression), classify it honestly.
5. **The meta-rule for "make it spotless under `-p randomly`":** the dominant 1–2 classes are usually
   by-construction-fixable (snapshot/restore at the right scope) and sweep 70–80% of failures in one go;
   then re-run the seed sweep and the TRUE residual (the genuinely-separate mechanisms) is what's left.
   Don't chase individual leaker→victim pairs (each probe is a 5-min full-suite run and a guess); fix the
   *class* at the shared fixture, re-run, repeat. Phase-0 the seed set as a contiguous range `1..N` (not
   cherry-picked) and instrument the per-seed *cluster* histogram — the failure COUNT varies by seed but
   the mechanism set converges, and a reviewer will (correctly) gate "reduces to exactly K classes" on
   that histogram, not on seed 1 alone. **Re-runnable probe:** `scripts/random-order-cluster-histogram.sh
   <test-dir> [N]` runs a contiguous `1..N` seed range single-process and prints, per seed, the pass/fail
   total + a per-file cluster histogram (set `PYRUN` for venv/isolated-env invocation). Use it for the
   Phase-0 sweep and again after each by-construction fix to read the shrinking residual.

### 5f. Thousands of ERRORS (not failures) in a single-process run = ONE resource ceiling, not N bugs

When a big single-process test run (a whole subsystem, the full suite) produces a *wall* of **errors**
— note: errors at *setup/teardown*, not assertion *failures* — the overwhelmingly likely cause is a
single **resource ceiling hit mid-run**, not thousands of independent bugs. The classic on macOS is the
default **`RLIMIT_NOFILE = 256`** (file-descriptor limit): a 3000-test single-process gateway run
accumulates open sockets/db-handles/temp-files past 256 and every subsequent test dies with
`OSError: [Errno 24] Too many open files` — which surfaces as scary cross-cutting errors in unrelated
adapters (email/feishu/… "failed to send /tmp/…"). **Real case (2026-06-22 QA campaign): 2288 "errors"
collapsed to 1 environment artifact + 0 product bugs** once the limit was raised.

The instrument-first protocol that separates "ceiling" from "N bugs" in minutes:
1. **Read the actual error text**, not just the count — `Errno 24` / `Errno 23` (file-table overflow) /
   `OSError` / `Cannot allocate memory` / `OperationalError: database is locked` all scream *resource
   ceiling*, whereas `AssertionError` screams *logic*.
2. **Re-run with the ceiling raised** (`ulimit -n 65536` for FDs; more RAM; serialize DB access). If the
   wall of errors vanishes and you're left with a handful, those few are the real signal — triage *them*
   in isolation (per §5e).
3. **Fix the ceiling at the harness, not the symptom:** raise the soft FD limit in `conftest.py`'s
   `pytest_configure` (toward the hard cap) so single-process / pollution-sweep runs work; the per-file
   CI runner (fresh interpreter per file) never hits it, so it's purely a single-process-runner gap.
   RED-prove the fix (revert → a guard test asserting the raised limit goes red).
Don't "fix" 2000 tests; fix the one limit. And don't dismiss the run as "too big to run in one process"
— raising the limit makes the single-process pollution sweep *possible*, which is what surfaces the real
cross-file leaks underneath (§5e).

### 5g. A feature \"isn't rendering\" → grep the LIVE log for its silent-degrade reason at the trigger timestamp (don't re-derive from source)

When a user reports a feature output looks wrong/missing — \"this is the plain form, where's the detail?\", \"that field is blank\", \"it fell back to X\" — and the feature has a **try/except → simpler-form** or **validate()-then-degrade** path, the fastest root cause is NOT reading the source to reason about which branch fired. It's **grepping the live log for the degrade-reason marker around the timestamp of the event the user pointed at.** A well-built degrade path logs a loud, greppable reason on every fall-back (it must — a silent degrade is undebuggable); that log line usually contains the exact arithmetic/identity that failed.

Real case (2026-06-22): the granular compaction announce shipped the two-line fallback in Discord. Instead of theorizing about `build_hygiene_stats`, one grep of the gateway log at the message's timestamp returned `COMPACTION_STATS_RECONCILE_FAILED hygiene token pre: cleared 302576 + folded 49924 + kept 3059 != pre 534788 (tol 8)` — the root cause (a ~179K-token partition gap on the LCM path) was visible in the first 30 seconds, no source spelunking.

The protocol:
1. **Get the timestamp of the user's example** (the Discord/Telegram message time, the run id) and convert to the log's timezone.
2. **Grep the live log for the feature's degrade/error marker** in that window: `grep -rh '<DEGRADE_MARKER>\|<feature-error-string>' ~/.hermes/logs/ | tail`. The marker is the loud string the except/validate-fail branch logs (`*_RECONCILE_FAILED`, `*_FALLBACK`, `degrading to`, the validate() reason text).
3. **Read the reason — it usually IS the diagnosis** (a failed identity, a missing key, a raised exception type), so you skip straight to Phase 2 on the right component.
4. **Then quantify dark-ness:** `grep -c '<success-marker>' log` vs `grep -c '<fallback-marker>' log`. Success-count 0 = the feature has been dark since it shipped (the production-dark trap; see `prd-closeout` common-failures).

Corollary for anything you BUILD with a degrade path: make the degrade log a unique greppable marker with the failing values inlined — that one line is what turns a future \"why is this blank?\" into a 30-second answer instead of a source-reasoning session. A degrade that logs nothing guarantees the feature goes dark unnoticed AND is undebuggable when finally caught.

### 5h. A feature that degrades on a SWALLOWED exception, logged at DEBUG, whose trigger is an INPUT-SHAPE the tests never feed → reproduce on the REAL shape, not the convenient one

§5g assumes the degrade logs a loud (WARNING/ERROR) greppable reason. The nastier variant: the degrade path catches a broad `except Exception` and logs the failure at **`debug`** — invisible in a normal (INFO) gateway/app log — so §5g's grep returns nothing and the feature is dark with NO trail. And the reason it crashes is almost always an **input-shape mismatch the unit tests don't exercise**: the tests build the *convenient* shape (a flat `content` string, a uniform-case token, a 2-element list), while production feeds the *real* shape (a `content` LIST of API blocks `{type: text|tool_use|tool_result}`, mixed-case, an empty/None edge). Every test passes; production silently degrades 100% of the time.

Real case (2026-06-22, in-turn compaction announce): the granular multi-line announce rendered ONLY on the hygiene path, never on the dominant in-turn (threshold) path. Root cause: `build_inturn_stats → _is_summary_message` did `regex.search(content)`, which raises `TypeError: expected string or bytes-like object, got 'list'` when `content` is a list of content blocks — the live in-turn shape. The caller's `try/except` swallowed it (`stats=None`), logged at `debug`, and `_format_compaction_announce` fell back to the single-line form. The hygiene path worked because it operates on flat `{role, content:str}` dicts; the in-turn path passes the raw API messages where `content` is a block list. Every unit test used flat-string fixtures, so the suite was green while the feature was dark since it shipped.

The protocol when §5g's log-grep comes up EMPTY but the feature is clearly degrading:
1. **Grep the source for the swallowing `try/except` around the producer**, and check its log LEVEL — a `logger.debug(...)`/`exc_info=True` in the except is the invisible trail. (Bump it to `warning` temporarily, or just read it.)
2. **Reproduce the producer on the REAL input shape, not the test's shape.** Pull a realistic message/record from the live path — for LLM message lists that means `content` as a LIST of blocks (`[{type:text,text:...}, {type:tool_use,...}]`, `[{type:tool_result,...}]`), NOT a flat string. Run the producer; you'll get the actual `TypeError`/`KeyError` the swallow hid. (`execute_code` with a hand-built list-content fixture reproduced it in one call here.)
3. **Confirm the test fixtures are the convenient shape.** If `grep` of the test file shows only `content="..."` (string) where production sends `content=[{...}]` (list), the green suite proves nothing about the real path — that's *why* it shipped dark. The fix's regression test MUST use the production shape (list content) and the function MUST coerce/handle it (extract text from blocks; treat list/dict/None as a real case), not assume a string.
4. **Fix the WHOLE shape class, and apply it to every sibling path that classifies the same data.** Here `_is_summary_message` (summary detection) AND `_tool_other_split` (tool-vs-other breakout) both keyed off the flat shape — the summary one *crashed*, the tool one *silently mis-bucketed* (tool RESULTS are `role=user`+`tool_result` block, not `role=="tool"`, so the whole population read as \"other\"). A `role=="tool"`-only classifier misses the block shape; recognize `tool_use`/`tool_result`/`tool_call` blocks too.

The meta-rule: **a swallowed-exception degrade is a §1 \"read the error\" you've been DENIED — un-swallow it (read/raise the real traceback) before theorizing, and reproduce on the input shape PRODUCTION sends, which for API-message pipelines is list-of-content-blocks, not the flat string your tests use.** Same family as the casing-collision transform bug (Phase 4: \"the test suite only used lowercase fixtures\") and the swallowed-error fake-FAIL factory — the fixture diversity *is* the test.

### 5i. A bug fixed on ONE of two TWIN/sibling producers is a HYPOTHESIS to check on the other — never proven-absent (2026-06-26)

When a system has **two parallel code paths that do the same job on slightly different inputs** — a hygiene-path vs in-turn-path stats producer, a read-path vs write-path validator, a CLI vs gateway entrypoint, an OpenAI-wire vs Anthropic-wire adapter — and you fix a bug in one, the closeout instinct is to assert the twin is fine \"because its data is already in the right shape.\" **That assertion is a hypothesis; check it against the twin's actual inputs.** Real case (PR #84/#101 → #106): the two-population `kept` bug (`folded` measured pre-side, `kept` measured comp-side → reconcile fails when a sanitizer mutates the kept tail) was fixed in `build_hygiene_stats`, and that closeout explicitly recorded *\"`build_inturn_stats` is correct — its `kept_rows` is already comp-side.\"* True for the POST identity, **FALSE for the PRE identity** — the in-turn twin had the identical bug on the *dominant* path, silently degrading every real session for days. The fix on the sibling didn't transfer because the one structural difference between the twins (in-turn sanitizes the kept tail; hygiene's content-signature pairing assumes it doesn't) was exactly the thing that broke the shared mechanism. **Protocol: when you fix bug B in producer P1 and a twin P2 exists, (1) grep for the twin (`grep -rn 'def build_' / both call sites`), (2) name the ONE input/shape difference between P1 and P2, (3) feed P2 the shape that triggered B and run its self-check — don't reason \"it's the same code so it's fine.\" Add a cross-link comment in BOTH so the next author touches both.** The tell you skipped this: the user reports the \"already-fixed\" bug again, on the other path.

**Companion technique — to model a TAIL-GLOBAL transform, replay the REAL batch function over a candidate slice; never a per-row stand-in.** When you need to reverse-map an output back to its input (find which raw rows produced a transformed tail, align a compressed slice to its source), and the transform operates on the **whole input as a set** — it drops rows, inserts synthetic rows, re-pairs/re-orders across the batch (here: LCM's `_sanitize_tool_pairs` drops orphan tool-results and *inserts stub tool-results* for calls whose results fell out of window) — then a **per-row predicate cannot reproduce it** (a per-row check can't know a stub will be inserted, because that decision depends on other rows in the tail). The sound mechanism: **replay the actual batch transform over candidate input slices and accept on EXACT equality of `transform(input[cut:]) == observed_output`** — search the cut from the expected boundary outward (common case = 1 replay). Accept-on-equality makes a wrong alignment structurally unable to pass (it can't \"reconcile by a token sum\"); no slice matches → fail safe (degrade). This is the same family as the §5h list-vs-string shape trap and the §1 \"reproduce on the REAL shape\" rule, applied to *reverse-mapping*: model the transform with the transform, not a hand-rolled approximation of it. Worked example + the 4-pass review that caught a per-row first attempt as unsound: `hermes-compression-ops` SKILL (PR #106 entry).

**🔴 A self-check that asserts a value the producer DERIVED as that very sum is a TAUTOLOGY — it can never fail (2026-06-22).** When a producer computes a "total" as `a + b + c` and its validator then asserts `total == a + b + c`, the check is vacuously true and guards NOTHING — a partition bug in `a`/`b`/`c` sails through because the total moved in lockstep. Real case: `build_hygiene_stats` set `post_messages = kept + summary + anchor` and `validate()` asserted exactly `post_messages == kept + summary + anchor`; the message-axis partition was wrong (a sanitized kept tail under-counted `kept`) and the tautology never tripped — it only surfaced when a *different* fix flipped the gate green and the wrong value rendered to the user (`Messages: 7748 → 1 (kept 0 recent chat)`). **Rule: a reconciliation identity only has teeth if BOTH sides are measured INDEPENDENTLY from the source.** Measure the total from the source population (`post_messages = len(comp)`), then assert it equals the sum of the independently-measured parts. Test for teeth by corrupting EACH part alone and confirming the identity fails (if corrupting a part doesn't break the check, the check is derived-from-that-part and dead). Companion to the dead-guard trap (deriving one bucket as `total − others`) — same disease, opposite end: there you derive a *part* from the total; here you derive the *total* from the parts. Either way one side isn't independent and the cross-check is theater.

**🔴 A magnitude/safety GUARD whose own input COLLAPSES on the exact failure it guards is theater (2026-06-27).** A close sibling of the tautology trap, hit twice by an external reviewer on one guard. When you add a \"is X small/safe enough to proceed?\" gate (render-vs-degrade, retry-vs-abort, fast-path-vs-slow), the gate is only sound if the quantity it measures is still **correct in the branch where the thing it measures went WRONG**. Real case: an \"is the approximate split safe to show?\" guard keyed off the *computed* kept-tail size — which **collapses to 0 exactly when the signature-match (the failure the guard exists to catch) fails** → guard reads \"0% → safe\" on the worst case and renders confidently-wrong output. First fix (use the comp-side size) *also* under-reported when a sanitizer stripped the tail small. The durable fix is a **match- AND transform-INDEPENDENT** bound — here `estimator(raw_input[-N:])`, computed straight from the raw suffix, immune to both match-failure and stripping. **Rule: before trusting a guard, ask \"what does my guard's input read in the branch where the underlying operation failed?\" — if it reads small/zero/safe precisely then, the guard can't fire when it must.** Pick a denominator that does not degrade with the failure.

**Proving the fix ORGANICALLY (not just \"the formatter renders my synthetic stats\").** A self-built fixture round-tripping proves the *format*, not that the *live system produces it on the real path* (the synthetic-render false-success trap, below). For a feature gated behind a runtime trigger (a compaction threshold, a queue depth, a size limit), prove it by **driving the real engine to its real terminal status on real data, then rendering ITS output through the real done-site** — on a non-user-facing rig. Full recipe (find the RIGHT threshold knob — an engine often has its OWN, e.g. LCM's `context_threshold`/`fresh_tail_count` ≠ the generic `compression.threshold`; build real list-content input via the real surface; assert the engine reaches the *terminal* status not a `noop`/lifecycle banner; render its real before/after; restore the rig config + confirm 0 new errors; and the live-import deploy/restart note): `references/degrade-on-live-data-shape-not-test-shape.md`.

**🔴 A custom transport ADAPTER that rebuilds request kwargs by allowlist can SILENTLY DROP a control kwarg the generic client would have honored — so a config knob is DEAD on that transport and nobody notices (2026-06-25).** When a "the timeout/retry/header isn't applying" symptom lands, the reflex is to check the config value or the client construction — but if there's a **transport adapter** between the caller and the SDK (an OpenAI-shape shim over a native Anthropic/Gemini/Bedrock client), that adapter often rebuilds the outbound request from a *hand-picked allowlist of keys* and **omits the one you care about**. Real case: the compaction summarizer hung ~30 min on a saturated relay; the assumed cause was "no `max_retries` on the client." The actual cause (found by a held-open-socket fault-injection rig, not by reading the value) was that `_AnthropicCompletionsAdapter.create()` built `anthropic_kwargs` from a fixed set of keys and **never read the caller's `timeout`** — so the 300s aux timeout never reached the native client, which used the SDK's 900s default, and `max_retries=2` multiplied it. The config knob had been *dead on the anthropic transport the whole time* while the OpenAI-wire path honored it fine (which is why a code-read of the OpenAI path "confirmed" the wrong mechanism). **Rule: when a per-request control (timeout/retries/headers/stop/etc.) "isn't applying," check whether an adapter in the path REBUILDS the request and drops it — grep the adapter's `create()`/`_build_*kwargs` for the key; don't assume the value the caller set reached the wire.** And prove it on the real adapter with a fault-injection rig (held-open socket for a timeout), not a unit mock that re-implements the adapter. Fix lived in ONE route-scoped adapter change (thread the dropped kwarg + `.with_options()` for the one task) — PR <owner>/hermes-agent#103.

### 5j. A periodic/throttled operation that re-fires EVERY run → its reset condition is one the bounded job can NEVER satisfy (2026-06-26)

**WHEN a job that's supposed to do an expensive thing only *occasionally* (a weekly safety-net full
walk, an N-day cache refresh, a periodic deep re-scan, a rate-limited retry) is instead doing it on
EVERY run** — the symptom is usually a cost/volume smell the user catches in a heartbeat ("why is the
nightly ingest reading 947 items for 18 new?", "why does this re-index every time?"). The bug is almost
never the *cadence check*; it's that the **timestamp/flag the cadence reads is never getting updated**,
because the code only stamps it on a **completion condition the bounded job structurally cannot reach.**

The classic shape: `shouldDoExpensiveThing = (now - lastDoneAt) > INTERVAL`, and `lastDoneAt` is stamped
**only when the operation runs to its absolute terminal state** (reached the end of the corpus,
`nextCursor === null`, queue fully drained, walked to the frontier). But the daily job runs under a
**budget cap** (`--max-pages 5`, a row limit, a time box) that is *smaller than the corpus* — so it can
never reach that terminal state, never stamps, and the cadence reads "overdue" forever. The expensive
op fires every single run and silently never self-heals.

**Real case (siftly nightly ingest):** the early-stop optimization shipped 2026-06-15 was dead the next
day. `lastFullWalkAt` was stamped ONLY for a source whose walk hit `nextCursor === null`. But the daily
job reads `--max-pages 5` against a 2,740-bookmark / 913-like corpus (~28 / ~10 pages to exhaust) — a
5-page walk can NEVER exhaust → `lastFullWalkAt` froze at 6/15 → `shouldFullWalk()` returned true every
night → ~950 reads/night instead of ~190 for ~11 straight runs. The DB told the whole story:
`runCount=24, lastFullWalkAt` stuck at the second run.

**The diagnostic shortcut (minutes, not source-spelunking):**
1. **Read the persisted cadence state directly.** `sqlite3 db "SELECT ..., lastDoneAt FROM stateTable"`
   (or the JSON/redis key). A timestamp **frozen far in the past while `runCount` keeps climbing** is the
   smoking gun — the op runs but never records "done."
2. **Find where that timestamp is written** and read its GATE. If it's gated on an *exhaustion/terminal*
   condition (`=== null`, "frontier reached", "queue empty") AND the job runs under a budget cap, ask:
   **can this job, at its cap, ever hit that condition on the real corpus?** Compute `corpus_size /
   page_budget` — if it's > the cap, the answer is no, and you've found it.
3. **The fix separates two conflated concerns:** "reached the ABSOLUTE terminal state" (a
   backfill/recovery semantic) vs "performed THIS periodic bounded operation" (the cadence semantic). The
   bounded periodic op IS the throttled thing doing its job; once it **completes its budgeted run
   cleanly** (ran to its cap or exhausted — excluding genuinely-incomplete runs like credit-depletion /
   interruption), its *cadence* must reset, regardless of absolute-terminal. Keep the terminal signal
   around (`perSource[s].nextCursor`) for whatever genuinely needs it; just stop using it as the cadence
   gate.
4. **Repair the live state too**, don't only ship the code — a frozen timestamp stays frozen until the
   next run; stamp it to now (with a backup) so the cheap path engages immediately instead of taking one
   more wasteful run to self-heal.

**The meta-tell for review:** an Opus/careful review that *deliberately* narrowed a stamp to
"exhaustion-only" to avoid resetting cadence on an incomplete recovery is the exact change that creates
this trap when the same code path also runs under a budget cap. A reset condition is only correct if the
job can actually *reach* it under its real operating limits — verify that, don't just verify the
condition is "more conservative." Related but distinct from §5c (sampling a flapping state) — this is a
*reset/completion* condition the job can't satisfy, not a *sampled* state that flaps.

**🛡️ THEN HARDEN: a "✅ OK" heartbeat that's silent about COST/RATIO let this hide for ~11 days — add a
runtime watchdog on the cheap-path invariant so the class fails LOUD within ONE cycle.** Fixing the
specific bug is half the job; the reason it survived ~11 nightly runs is that the heartbeat said
"✅ Daily ingest OK" the whole time — *a successful run is not necessarily a CHEAP or CORRECT run, and
nothing was watching the ratio.* When you fix a silent-waste / silent-degrade class (this §5j cadence
trap, a cache that stops being warm, an early-stop/short-circuit that silently stops engaging, a "should
be incremental" job doing full work), add the missing watchdog in the SAME change so a regression can't
re-hide:
1. **Emit a structured, grep-stable telemetry line** from the operation that names the cheap-vs-expensive
   signal AND why (`early-stop-telemetry: engaged=<bool> reason=<safety-net|kill-switch|none>`). One line,
   parseable, on every run. This is the per-run truth the heartbeat's calm ✅ omits.
2. **Add a pure, unit-testable detector for the invariant's VIOLATION**, not for the happy path. Frame it
   as "this run did expensive work it had no legitimate reason to do": e.g. reads ≥ X% of the full-work
   ceiling (`budget × sources`) AND the cheap path did NOT engage AND no exempt reason
   (safety-net/kill-switch/known-fallback are explicitly exempted so legit-occasional expensive runs stay
   quiet). Test the EXEMPTIONS as hard as the trigger — a guard that also fires on the legitimate weekly
   sweep gets muted and becomes useless.
3. **Route a violation to a LOUD alert WITHOUT failing the run** — it's a warning, not a crash; the run
   still succeeds, but the anomaly is now visible in the alerts channel the next morning instead of after weeks.
4. **The guard IS the regression test for §5j's whole class** — it catches not just this cadence bug but
   any future "the cheap path silently stopped being cheap" (probe returns empty, flag never flips,
   short-circuit disabled). The lesson distilled: **"✅ OK" must mean cheap AND correct, not just
   "didn't crash" — if a green run can secretly be 5× the cost, the heartbeat needs a cost invariant.**
   (Worked example: siftly `daily-ingest.ts` `detectReadAmplification()` + `ingest.ts`
   `early-stop-telemetry` line, 2026-06-26 — 11 detector+e2e tests covering trigger, every exemption, and
   the boundary.)

### 5k. A monitor/watcher firing on "production" markers that are actually TEST EXHAUST — the real bug is a test writing to the live log, not the watcher (2026-06-27)

**WHEN a log-grepping watcher/cron pages on `<MARKER>` warnings and you're about to either (a) triage them as a production regression or (b) "harden the watcher's filter" to ignore them** — FIRST classify whether the markers are real production events or **test-run exhaust written into the live log.** The tells that a marker is a pytest fixture, not a real event: `engine=<MagicMock …>`, `model=test/model`, `session=S1`/`S2` (synthetic ids), hard-coded fixture arithmetic that **repeats byte-identical across timestamps** (`cleared 999 + folded 300 + kept 32` three times = replayed fixtures, real turns never produce identical token counts), impossible shapes (`pre 11` with a 424-row kept tail), and session ids **absent from the live `sessions.json`**. Real production markers carry realistic magnitudes, a real bound session id, and never repeat exactly.

**The trap I fell into (own-goal): I asserted "pytest pollutes the live log" as the MECHANISM from the fixture-shaped content alone, then spent rounds whack-a-mole'ing the watcher's content filter** — which can't work, because the bare markers (`BUILD_FAILED in-turn`, `TAG_MISSING in-turn`) and realistic-magnitude fixtures are **content-identical to real degrades**; filtering them by content would blind the watcher to the real thing. Suppressing a marker you can't distinguish from a genuine failure is worse than the false page.

**The actual root cause (one layer deeper, only found by GROUND-TRUTHING the write path):** `hermes_logging.setup_logging()` attaches a `RotatingFileHandler` at `<home>/logs/agent.log` to the **root logger** (remembered via a module global). If a test builds a real agent or imports a module that calls it **before** the conftest `HERMES_HOME` redirect (an import-order race) — or `HERMES_HOME` resolves to the real home at that instant — the handler targets the **real `~/.hermes/logs`**, so every WARNING the test emits (e.g. `COMPACTION_STATS_RECONCILE_FAILED`) **appends to the production log**, which the watcher then greps. `caplog`-based tests don't leak (caplog uses its own handler); the leak is specifically tests that reach the root file handler.

**Protocol:**
1. **Classify the markers** by the test-fingerprint tells above before deciding it's a regression OR a watcher bug.
2. **Don't reach for the content filter as the primary fix** when the markers can be content-identical to real ones — a watcher cannot reliably distinguish them, so a filter is at best defense-in-depth (drop only the UNAMBIGUOUS fingerprints — `MagicMock`, `test/model`, the exact fixture triples — never a bare `BUILD_FAILED`).
3. **Find the actual write path.** Grep how the marker's logger reaches a file: a root-logger `RotatingFileHandler` whose `baseFilename` is outside the test sandbox is the leak. **Prove it RED→GREEN**: attach a real-home handler, emit a WARNING, watch the real log grow by N bytes; strip the handler, emit again, 0 bytes.
4. **Fix at the source** — an autouse conftest fixture that strips any root/named-logger file handler whose `baseFilename` is **not inside the per-test sandbox** (use real path-containment `Path(base).resolve().relative_to(sandbox.resolve())`, **NOT `str.startswith`** — a string prefix treats sibling dirs `/tmp/x/t0` vs `/tmp/x/t01` as inside; Greptile caught exactly this). Also reset `_logging_initialized` so a later `setup_logging()` re-attaches against the sandboxed home. This eliminates the whole class regardless of import order.
5. **Honest residual:** content-identical markers ALREADY in the log can't be told apart post-hoc, but an incremental watcher only reports NEW markers per run, and the source fix stops new ones — so it self-quiets once the backlog rotates out. Note the limit in code; don't over-filter.

The meta-rule: **a watcher paging on test-shaped markers is a symptom of test→production log bleed, not a watcher-filter gap. Prove the write path (which file does the test's logger reach?) before patching the consumer (the watcher).** Same family as §5g (grep the live log) and the §1 "prove the mechanism, don't assert it from convenient evidence" rule — applied to *which process wrote the log line*.

### 6. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### 6. Distinguish provider failure from emulation drift

**WHEN debugging a proxy/bridge that emulates a real CLI/SDK:** separate these failure classes before fixing code:

1. **Quota/provider state** — e.g. usage-limit errors or subscription exhaustion.
2. **Credential-source drift** — real CLI succeeds because it refreshed Keychain/secret-store credentials while the proxy reads a stale file.
3. **Request transform drift** — fork output differs from upstream or from known-good fixtures.
4. **Real-client baseline drift** — CLI/SDK version changed headers, beta list, `stream`, user-agent, billing metadata, etc.

Use mock/offline instrumentation first:

- Compare fork vs upstream transform output on realistic fixtures.
- Capture the real CLI/SDK request against a local mock endpoint, redacting credentials.
- Normalize volatile values (`device_id`, `session_id`, UUIDs, billing hash suffixes) before diffing.
- Only run live probes after the offline diffs are understood.

For live probes, vary one wire-shape dimension at a time (`stream`, `accept`, beta list, token source, model). Prefer the cheapest model first; make expensive model probes opt-in.


### Honest verification of a shipped fix

When the user asks "did the fix work?" or "is it working now?", the bar is not "one `/health` probe returned 200." The bar is:

1. **Liveness check that distinguishes restart from steady state.** Look at `launchctl print` (or systemctl, or container restart count) for `runs = N` and the time the PID has been alive. A `/health` 200 between launchd restarts of a crash-looping process is a false positive — exactly the failure mode that embarrassed the 2026-05-14 session.
2. **Real-traffic evidence, not synthetic.** Captures in `/tmp/proxy-capture/` (or equivalent) showing the user's actual requests being served successfully, with `requestsServed` incrementing while the user is active.
3. **Log cleanliness after the latest version banner.** Grep for crash signatures (`SyntaxError`, `uncaughtException`, the original error string, etc.) in only the log segment after the version-banner marker. Old crash entries from the pre-fix process are not evidence of new failure.
4. **Honest reproduction or honest absence.** If you tried to build a synthetic repro of the bug and it does not reproduce on the pre-fix version, say so. You proved a *plausible* corruption path, not the exact prod trigger. The right next move is to extract the actual crashing payload from the capture dir or log and feed it through on the pre-fix version. That is a deterministic regression. Stop short of that and your "fix shipped" claim rests on real-traffic absence-of-crash for a few minutes, not on a regression test. This is OK when the user is unblocked, but be explicit about the gap so the regression test doesn't quietly never get written.

Code path: every shipped fix becomes a `test/parity/vX.Y.Z-*.test.js` regression file. If you cannot point to one for this fix, the fix is not done yet — it is staged.

### Two false-success traps that only behavioral testing catches

These bit a real session (2026-06) and both were caught ONLY because the verification probed *behavior*, not a tool's success claim or a self-supplied render. Internalize both:

1. **A patch/edit tool can report `success: true` while silently changing nothing.** A multi-block `patch` with `"""`-quoted Python docstrings in the old/new strings matched zero bytes (escaping mismatch) yet returned success; the file was unchanged. The next dry-run "passed" — because it was running the OLD code's output, which happened to look plausible. **Never trust an edit tool's success field. After any edit, re-read the changed region (`grep` for a token you just added) and confirm the new bytes are physically present before running anything downstream.** If a later test behaves like the edit didn't land, suspect a silent no-op patch first.

2. **Synthetic input rendering correctly is NOT empirical proof.** "I proved the new log field works" — by calling the format string in-process with a value I supplied myself, which trivially echoed it back. That proved the *format*, not that the live system *produces* that value on the real path. The production path never populated the field as assumed. **A self-constructed fixture that round-trips tells you the code can format/parse that shape; it tells you nothing about whether the real upstream emits it.** To prove a field/value is real, grep the LIVE artifact (log, DB, capture dir) for an actual production occurrence — zero hits means your assumption is wrong regardless of how clean the synthetic test is. This is the same class as the `/health`-200-between-restarts false positive: synthetic/steady-state evidence masquerading as proof of the real path.

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

**For transform functions (wrap/unwrap, encode/decode, escape/unescape, casing-preserving operations):** the regression test MUST exercise input diversity, not just one fixture. A casing-collision bug in this session shipped to production because the test suite only used lowercase inputs (`'calculator'`, `'bash'`), so a lowercase-first unwrap rule looked correct. Production used PascalCase tools (`'Glob'`, `'Bash'`) and the round-trip silently corrupted them. Minimum fixture set for a casing/format-preserving transform: lowercase-first, uppercase-first, snake_case, mixed-case, empty, single-char, already-transformed (idempotency), plus a `transform_inverse(transform(x)) === x` identity check across all of them.

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**
- **You are shipping a third revision of a fix for the same symptom, each with its own architecture story.** For LLM-in-the-loop systems this is the tell-tale sign that the original hypothesis was wrong and every "improvement" since has been refining the wrong model of the bug. See `references/instrument-before-guessing-when-model-is-symptom.md`.
- **Lifecycle telemetry looks healthy but symptom persists.** `[ScriptName] attached`, `observer registered`, `middleware loaded`, `subscribed to events` — none of these prove the work loop ever did work. If your only telemetry is at the install layer, you cannot distinguish "selector matched zero elements" from "script failed to load," and you will burn hours on the wrong hypothesis. See `references/log-effect-not-lifecycle.md`.
- **Remote Windows display debugging:** when a Windows machine is alive over SSH/RDP but the physical monitor black-screens/blinks after GPU, cable, adapter, or refresh-rate changes, separate host health from display-path health before changing drivers. Probe video controllers, PnP monitors, WMI monitor connection params, `nvidia-smi`, and recent display/PnP events; then test one cable path at 4K60 SDR before adding HDR/VRR/high refresh. See `references/windows-remote-display-black-screen.md`.
- **DP-to-HDMI DRR/VRR debugging:** if native DisplayPort supports DRR/VRR but an active DP-to-HDMI adapter does not, do not blame the GPU first. Check adapter firmware/bridge-chip support and whether Windows/NVIDIA sees VRR capability at all. See `references/displayport-hdmi-vrr-adapters.md`.

- **You were handed a root-cause writeup + an approved fix and are about to "just implement it."** A handed-off diagnosis (from another agent, a teammate, a past session, or your own earlier reasoning) is a hypothesis. If you haven't re-derived it from the raw logs/metrics it was built on, you don't know the mechanism — and the approved fix may be tuned against the wrong one. Three even 90s timing gaps mean a 90s timer, not the 120s watchdog the writeup blamed. See `references/verify-handed-off-diagnosis-against-logs.md`.

- **You're about to explain an `attempted=N / succeeded=M` gap as failures** (or any "X out of Y didn't work") from the number alone. The "succeeded" counter may only tick on a non-empty result, not on absence-of-error — the gap can be benign empties. A loop with no per-item catch that ran to completion means *nothing errored*. Read the loop and inspect the actual gap items before asserting a cause. See `references/count-gap-and-enriched-not-indexed.md`.
- **You added an enrichment/derived field and assumed it's searchable** without tracing it to every consumer (FTS builder, embedding-input builder, export, ranker). A field in one search leg but not the others is a silent half-wired feature. See `references/count-gap-and-enriched-not-indexed.md`.

- **You're about to restart/`kill` a long-running throughput job because it "looks stuck"** (0% CPU, no active children, flat counter over a couple of snapshots). Bursty jobs (ingest, crawler, transcription, queue drainer) read idle at the instant you sample the trough. Measure the durable progress signal over a window sized to the job's *known* cadence (5–15 min, not 2–4) before concluding wedged — and if you've already killed it 2+ times and each kill is your only new "evidence" of a stall, you manufactured the symptom. See section 5d. **ALL of these mean: STOP.**

- **A fan-out pipeline (multi-lane/proxy/replica/backend/POP) "isn't progressing" and you're about to conclude "we're rate-limited / blocked / just rest it a day."** Two stacked illusions make that wrong and expensive: (1) the recorded "failures" are often your OWN governor/LB giving up (`all lanes cooling`, `circuit open`, `no healthy upstream`) — not the upstream's rejection; (2) paths fail INDEPENDENTLY, so "everything's blocked" is rarely literal — a shared governor cools the one WORKING path along with the bad ones and hides it. Don't theorize: **actively probe EACH path with the REAL operation against a REPRESENTATIVE workload item** (a generic/popular item or a `/health` ping gives a FALSE GREEN — it rides the unguarded path your real items don't). Classify each path with an actionable verdict + remedy, route through the ones that `work`, rest only the genuinely-blocked. Capture it as a re-runnable doctor reusing the prod classifier. See `references/per-path-probe-aggregate-failure-and-representative-input.md`. **STOP and probe before you "wait it out."**

- **You fixed a real bug but the live symptom persists, and you're about to say "fixed / it's working" — or invent a deeper bug in the file you just edited.** Two traps: (1) **the running daemon imported its code AT START** — if you edited after it launched, it's still executing the OLD bytecode (compare `ps -o lstart= -p <pid>` to the edited file's mtime; restart before judging). (2) **one symptom can have N independent root causes stacked in series** — each fix only EXPOSES the next layer, and the same fragile op often lives at MULTIPLE call sites (`grep -rn '<the call>' src/` before claiming done). "Fixed" is earned ONLY when the user-visible COMPLETION signal moves on the REAL production path — not when an isolated e2e passes or an intermediate signal (bytes moving) looks good. Say the honest in-between ("downloads complete but transcripts still aren't finalizing — another layer") instead of a premature "fixed"; serial false "fixed" claims destroy trust fast. See `references/multi-layer-fix-and-stale-process-traps.md`.

**ALL of these mean: STOP. Return to Phase 1.**

- **A metric reads 0/N (or all-fail), or a per-trial field holds a stringified error string, and you're about to theorize about WHY the behavior failed.** A broad `except Exception` that turns an error into a score/field is a **fake-FAIL factory**: it converts a *structural* break (wrong interpreter, broken import, missing dep) into a *behavioral* zero, and you'll "fix" the wrong layer. Your FIRST move is to re-raise / `traceback.print_exc()` and read the ACTUAL stack — don't trust the swallowed string. A clean uniform 0/N points at the RIG, not the system under test. If subprocess runs fail but in-process/`execute_code` probes pass, suspect the subprocess's interpreter/env (`which -a python3`; pin the venv). Real example where I burned two wrong fix rounds (incl. shipping an unrelated "fix") before forcing the traceback revealed an anaconda-3.7 import death: `references/swallowed-error-as-fake-fail-force-the-traceback.md`.

- **You attributed a cause from a stale COUNT or a prior memory note, without checking the TIMESTAMP or the CURRENT state.** A log count returning a big number ("453 refs, 359 429s — must be the other actor") is NOT evidence the events are recent or relevant: the count is silent about WHEN. Pattern-matching that count onto a prior belief (a memory note like "two bots in one channel = the known footgun") is a *convenient verdict*, not a finding. Before naming a contributing actor: (1) read the actual first+last **timestamps** of those events (the terminal compressor truncates head/tail output, so re-run cleanly); (2) check the **current authoritative state** that governs whether the actor can even still act (permissions, config, ACLs — not week-old logs). Real failure (the orchestrator agent, 2026-06-20): blamed a co-located bot for a stuck typing bubble off a 453-ref/359-429 count + a memory footgun-note; the user pushed back with a permissions screenshot — all 359 events were **5 days stale** and the bot had **no channel access**, making it a non-factor. The user's own-eyes correction was right; the convenient "it's the other bot" verdict was wrong. **Logs prove what happened, not what's true now — ground-truth current state before attributing, and reconcile a user's contradiction instead of defending the easy answer.** Full recipe: `references/stale-count-and-current-state-attribution.md`.

**ALL of these mean: STOP. Return to Phase 1.**

- **You're about to write "terminal / WONTFIX / can't recover / data is gone / impossible / BACKLOG" in a closeout.** That verdict is a hypothesis, not a finding — and a probing user will test it. Before shipping it: check disk for the data you'd have to re-fetch (it's often already saved), re-derive the root cause on the REAL records (a flag's reason string is a symptom; one label hides N fixable causes), and scope the real risk vs. the named risk. Only a *measured* impossibility (state the number) is a real WONTFIX. Real session: 2 of 3 closeout WONTFIX calls were wrong. See `references/wontfix-terminal-is-a-hypothesis-ground-truth-it.md`. **STOP — ground-truth before you write it off.**

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |
| "This one's clearly terminal/WONTFIX, no point checking" | A terminal verdict needs evidence like a fix needs verification. Check disk, re-derive the cause, scope real risk — 2/3 such calls were wrong last time. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## When to delegate an ephemeral debug subagent

Debugging is a SKILL you run inline by default — you fix as you find, in a tight loop, holding the
context. **There is no standing debug agent.** But for three specific situations, the orchestrator (or a
coder) should delegate an **ephemeral** debug subagent (`delegate_task`, no profile) that investigates
and **returns findings — it does NOT fix**. The caller synthesizes and applies the fix. Delegate ONLY on:

1. **Context-threatening dive** — a root-cause investigation whose log/probe/trace noise would blow the
   caller's context window (long `journalctl` sweeps, byte-capture dumps, a wide multi-service trace).
   Isolate the noise in a subagent; get back the conclusion, not the 50k tokens of raw evidence.
2. **Rule-of-Three stuck bug** — after 3 failed fixes (see Phase 4), the original hypothesis is probably
   wrong and you're refining the wrong model. Spawn a **fresh-eyes** subagent that did NOT form the
   original hypothesis (Agans' "get a fresh view") and give it the primary evidence, not your theory.
3. **Parallel-hypothesis fan-out** — when there are N independent candidate root-causes worth testing at
   once, dispatch one subagent per hypothesis in parallel; each reports support/refute with evidence.

The subagent gets a **standalone brief** (it can't see you): the symptom, the exact reproduction, the
evidence/files, and "follow systematic-debugging Phase 1; report root-cause findings with evidence; do
NOT fix." Right-size it — a single inline investigation is cheaper than a fan-out; reserve delegation for
when one of the three triggers genuinely fires (the SOUL delegate-vs-do rule).

> **Boundary — debug diagnosis vs QA verification are SEPARATE, not one combined agent.** An ephemeral
> debug subagent is *white-box*: deep source context, traces the data flow, finds WHY. QA verification
> (the `qa` skill / the the QA agent verifier) is *black-box*: no source assumptions, exercises the real path,
> certifies WHETHER it works. Opposite context needs — don't fuse them.

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**

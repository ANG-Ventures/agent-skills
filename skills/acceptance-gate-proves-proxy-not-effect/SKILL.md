---
name: acceptance-gate-proves-proxy-not-effect
description: >
  Load when a physical/integration/E2E acceptance gate goes GREEN and you're about to close a
  "records / persists / emits / writes X on every turn"-class feature on the strength of it. Its job:
  catch the case where the green gate proved a PROXY (the speaker made noise, the endpoint returned 200,
  the process stayed up) but never exercised the code path that produces the named side-effect. Triggers:
  "acceptance PASS", "7/7 green", "wake→HEAR passed", "gate is green so it's done", closing a
  turn-completion sink / recorder / card-emitter / metrics-write feature, "acceptance.sh passed",
  "does the gate actually prove the feature". Editable, fleet-owned companion to the read-only
  verifying-beyond-green-tests (Seam 5) and closeout-ops.
version: 1.0.0
---

# Acceptance Gate Proves a Proxy, Not the Effect

A passing acceptance / physical E2E gate proves **the stimulus it drove reached the assertions it makes.**
It does NOT prove a feature whose code path sits *downstream of or beside* that stimulus. The trap: you
close a "does X on every turn/request/event"-class feature because the gate is green, but the gate never
completed the path that produces X. The green is a **proxy** (something happened), not the **outcome**
(X happened).

## The one-line tell
**Trace the gate's driven stimulus to the exact frame/event/write your feature hooks. If the gate stops
UPSTREAM of that hook, its PASS is a proxy for your feature — it would pass identically whether your
feature worked or was deleted.** That's the same tell as unit-green blindness, but at the acceptance tier.

## Why acceptance gates lie here
Acceptance gates are scoped to the CHEAP-to-drive, reliably-observable stimulus — which is frequently
upstream of the real side-effect:
- A voice gate drives a **wake** (DETECT → arbitration → beep → announce burst, all acoustically checkable)
  but does NOT complete a **command turn** — camera audio is a reliable *wake* stimulus but an unreliable
  *STT* stimulus by design (below the VAD gate). No turn completes → a turn-completion sink (recorder, card,
  metrics) writes nothing, yet every acceptance assertion passes.
- An HTTP gate asserts `200 OK` from a health/echo route, not that the request hit the handler that writes
  the row / enqueues the job / fires the webhook.
- A "process still alive after" gate proves no crash, not that the feature ran.

## Verified case (2026-07-01, the voice assistant flight recorder)
Full physical `acceptance.sh --room kitchen` → **7/7 PASS** (beep +31 dB, reply +42 dB, hub alive). But
`~/clanker-flightrec/<date>/` record count stayed **0**: the script only drives a wake, so zero
`house_pipeline_turn` completions, so the recorder — the whole feature being closed — wrote nothing. The
gate's PASS was a proxy ("the speaker made noise"). The real proof required a **human-spoken command turn**
("Hey the voice assistant, what time is it?" → "It's 5:11 AM."), after which a well-formed `record.json` + `post_vad.wav`
landed. That real record — watched for live with a count-delta — is what actually closed the work.
(Detail lives in the same repo's `docs/README-flight-recorder.md`.)

## Do
- **Name the side-effect first**, then verify the gate's stimulus reaches the code that produces it. If it
  doesn't, the gate does not test your feature — say so, don't close on it.
- **Assert the side-effect POSITIVELY, on representative input** — count/read the record, the emitted card,
  the metric row. Not "no error"; not an upstream health signal. A **safe-degrade** feature hides the miss
  hardest (nothing errors when it silently no-ops), so a happy-path smoke + a green gate both miss it.
- **Watch the write live with a delta check:** capture `before=N`, apply the REAL stimulus, poll the
  artifact dir / grep the completion log, assert `count > N`. "It wrote" becomes a checked fact, not a claim.
- **If the harness structurally can't drive the real path, that's a documented limitation, not a closeout.**
  Get the real stimulus (a human command turn, a real client request, a genuine event) and observe the
  side-effect. Don't let the harness's convenient proxy stand in for the outcome.
- **Update the deferred-work ledger honestly:** "acceptance PASS + real side-effect observed" is done;
  "acceptance PASS, side-effect unobserved" is a still-open leg, not a green.

## Sub-species: the gate's ASSERTION was authored by the thing under test (LLM-authored oracle)

The cases above are *stimulus upstream of the side-effect*. There is a second, sneakier species: the
gate runs the right stimulus and asserts the right kind of thing, but **an LLM wrote WHAT it asserts**,
so the gate can be satisfied by an artifact that never proves the property it names. A **deterministic**
gate is especially seductive here — "it's real pytest + a content-hash, no model at gate time" feels
un-fakeable, but determinism only buys tamper-proofing and no-model-at-replay; it does NOT buy that the
assertion checks the right thing.

Verified case (2026-07-01, autobuild v0.3 error-autofix): the certify oracle is a **frozen repro** — the
incident must go RED pre-fix, the repro is content-hashed (builder can't tamper it), and it must replay
GREEN post-fix. Fully deterministic. But the repro was **authored by an LLM**, so a weak repro
(`assert scale(3) != 5` for an incident whose correct value is 6) goes RED→GREEN on a *wrong* fix
(`x-2` → `scale(3)==1 != 5`). The green certify chain proved "the repro replayed", a proxy for "the fix
fixes the incident."

**The tell:** ask *"who authored the assertion, and could a wrong-but-plausible artifact satisfy it?"*
If the answer is "the LLM/builder under evaluation authored it," the gate is grading work the same
principal wrote — self-grading with extra steps.

**The fix — prove the oracle DISCRIMINATES via mechanical mutation testing.** The artifact is adequate
iff it's RED pre-fix, GREEN vs the real fix, AND stays RED against **every incident-triggering behavioral
mutant** — a *mechanical* (AST operator-swap, never hand-listed, never a no-op) source change that alters
behavior but leaves the effect unachieved (`a/b→a//b` still crashes on `b==0`). Two rules keep it honest:
a "no-op decoy" is a tautology (byte-identical to unfixed code = zero signal — use a *behavioral* mutant);
and gate the **mutator's own strength** — it must emit ≥1 incident-triggering mutant per case (filtered
through an independent effect-probe) or that corpus item FAILS, else the adequacy rate is measured over
gameable strawmen. Then **mutation-prove the discrimination loop itself**: neuter it and a weak artifact
must wrongly certify. Generalizes to any LLM-authored golden output / checker / assertion set. Reference
implementation: `~/.hermes/autobuild/consumers/autofix_adequacy.py` + `tests/test_autofix_adequacy.py`.

## Sub-species: the PROCESS-INTROSPECTION proxy — `ps`/argv lies about which interpreter/tree a live process uses

Inverse of the green-hides-a-miss trap: here a **red-looking proxy hid a real success**, and I almost
mis-closed a *working* migration as broken. Verified 2026-07-01 (desktop backend → runtime-venv migration).

After repointing the desktop backend to the runtime deploy venv and relaunching, `ps -o command=` /
`ps aux` showed the backend running `/opt/homebrew/.../Python -m hermes_cli.main serve` — i.e. **system
homebrew python, NOT the venv python** — which reads as "the migration didn't take." It had taken. A venv
created with `--symlinks` (the default) has `venv/bin/python → python3.11 → /opt/homebrew/.../Python`, and
macOS `ps` resolves argv[0] through the symlink chain to the **ultimate target**, so the command string
shows the homebrew interpreter even though `sys.prefix` is the venv.

**The tell:** proving "which python / which tree a running process uses" from `ps`/argv is a PROXY — the
argv path is cosmetic under symlinked venvs. The **effect** is which `site-packages` / import root the
process actually loaded.

**Prove it by what the process HAS OPEN, not what its argv says:**
- `lsof -p <pid> | grep site-packages` → count open files under the EXPECTED venv's
  `.../venv/lib/pythonX.Y/site-packages` and assert **0** under the wrong one. 42-open-under-runtime /
  0-under-dev is a checked fact; "argv shows homebrew python" is a red herring.
- Confirm the import ROOT via the process env: `ps eww -p <pid> | tr ' ' '\n' | grep -E 'PYTHONPATH=|PATH='`
  — PYTHONPATH pointing at the target tree + the target `venv/bin` first on PATH is the resolution proof.
- lsof-of-site-packages needs no cooperation from the process and is the strongest single signal.

Also verified same session: a symlinked venv python passes `fs.statSync(p).isFile()` (follows the link →
true) but FAILS `fs.lstatSync(p).isFile()` (the link itself is not a file). If an existence check on a venv
interpreter mysteriously "fails," check whether it's `lstat`-based before concluding the venv is broken.

Generalizes to ANY "is this process running the code/tree/venv I deployed?" question: **instrument the
loaded artifacts (lsof, /proc/<pid>/maps, open FDs), never trust the argv/command string** — symlinks,
wrappers, and re-exec shims all make argv lie. Same family as the "print what the interpreter actually
loaded" reflex when disk-truth and runtime-truth disagree.

## Sub-species: the SPEC-REVIEW proxy — an all-mock acceptance PLAN that structurally can't catch the load-bearing bug (caught before any code)

The cases above catch a proxy after a gate runs. This one catches it **at spec/PRD review, before a
line of code** — the acceptance *plan* is already a proxy. Verified twice in one session (2026-07-01,
Telegram redelivery-guard spec + restart-backfill-observability spec, both flagged by Opus review):

1. **An all-mock test tier proves the wiring, not the effect.** The redelivery-guard spec's tests drove
   the guard against a *mock* session store. But the load-bearing bug was an identifier-namespace
   conflation (`update_id` envelope vs `message_id` per-chat — see `identifier-representation-dedup-bugs`):
   a mock that echoes whatever id the author feeds it passes green, while in prod every real lookup
   misses → permanent silent no-op. **Fix: a Tier-2 LIVE-integration AC that persists through the REAL
   stamping path, drives a REAL event carrying its own distinct ids, and asserts the effect — plus a
   mutation feeding the WRONG id that MUST turn that live test RED.** An all-mock suite is a proxy for a
   feature whose bug lives at the mock boundary.
2. **"Source-inspected ≠ output-inspected" for a log-scrape / regex consumer.** The backfill-watch spec
   ground-truthed that the producer's emit *statement* existed (`git show fork/main:…adapter.py` had the
   `logger.log(... "PHASE=restart_backfill ...")` line) and treated that as "the emit is live." But the
   parser regex had **never seen the RENDERED line** — the actual `<ts> LEVEL [profile] logger: [<name>]
   PHASE=…` framing, level routing, record prefix. With **0** such lines in current logs, a format drift
   means the watcher passes its silent-on-healthy invariant **vacuously forever** and looks healthy while
   matching nothing. **Fix = a BUILD-GATE AC: capture one REAL emitted line (trigger the real stimulus —
   a safe-restart with a queued message), pin it as a fixture, and don't trust "green = healthy" until
   the regex has matched real output.** Proving the producer's code path exists is a proxy for proving
   the consumer parses its output.

**Generalized tell for a spec/plan:** ask *"if the load-bearing mechanism were completely broken, would
every listed acceptance test still pass?"* If yes — because the tests mock the seam the bug lives at, or
verify an upstream artifact (a source statement, a 200, a wake) instead of the rendered effect — the plan
gates a proxy. Require ONE test that runs the real path end-to-end against the real producer/store and
asserts the named side-effect, plus a mutation that breaks the mechanism and must turn THAT test red. For
a silent-on-healthy watcher, ALSO route total-miss/drift (raw marker seen but 0 parsed) to a human
channel — an unread stderr line + a "the cron ran" heartbeat together still hide a parser that matches
nothing. Fold these as ACs/RCs during review, not after the build ships green.

## Cross-refs
- `verifying-beyond-green-tests` (read-only in curation) — Seam 5 is the unit/integration twin of this.
- `closeout-ops` (read-only in curation) — Rule 9 (a degraded-but-safe fallback hides the miss; assert the
  feature POSITIVELY fires) is the same lesson at the closeout tier.
- `clanker-e2e` (read-only) — the voice-hub acceptance gate this trap was found on.
- `autobuild-new-loop` (external/read-only) — the LLM-authored-oracle sub-species was found building the
  autobuild v0.3 land cutover; that skill's cutover section names the same adequacy-gate pattern.

## Designing a NEW harness/gate so it can't fake-green (2026-07-02, voice-gauntlet review)

When BUILDING an autonomous verifier (not just closing a feature behind one), four patterns keep it honest
— each maps to a fake-green failure mode an Opus review BLOCKed on:

1. **Tri-state verdicts: PASS / FAIL / INCONCLUSIVE.** Anything the harness cannot SEE (proxy-only signal,
   empty timeline, dead rig, mis-aimed stimulus) is INCONCLUSIVE — never PASS. Binary verdicts force
   blindness into one of the wrong buckets.
2. **Proven-red before trusted-green (falsifiability).** A gate never observed red is unfalsified. Require
   an AC where the gate FAILS under the real prior defect — and prefer DEFECT-red over KILL-SWITCH-red:
   disabling a whole lane proves the invariant fires when the lane is dead, not that it fires on the subtle
   regression. Graduated fault-injection knobs beat feature kill switches. Fault knobs need their OWN tests
   (unset ≡ production; armed ≡ defect) independent of the gate that consumes them — a knob whose only test
   is "the test that needs it passes" is self-certifying.
3. **Contract-lock any log/text parsing.** Regex-over-logs dies silently: a log-string rename ⇒ empty
   timeline ⇒ zero violations ⇒ green. Keep an EMIT_CONTRACT map (parsed pattern → expected emitting source
   file) with a test that greps the real source tree, so renames fail the BUILD. Pair with a timeline-sanity
   floor (N stimulus acts ⇒ ≥ minimal expected events, else INCONCLUSIVE).
4. **One clock; achieved timeline over intended.** Never compare timestamps across hosts/clocks for
   sub-second invariants — derive all invariant math from the observed (journal) clock, and evaluate what
   actually happened (achieved stimulus times) rather than what the script intended.

Also: physical-rig harnesses need an UNCONDITIONAL start-of-run state reconciler (restore volumes, clear
staged media) — end-of-run cleanup doesn't run when the previous run crashed.

## Vendored references (folded from local overlay skills)
- `references/acceptance-gate-proves-proxy-not-effect.md` — Destructive-live-gate pitfall: running a load/stress AC against a shared user-facing service

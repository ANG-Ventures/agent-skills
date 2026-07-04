# Multi-layer fixes, the "edit-after-launch" stale-process trap, and serial false-"fixed" claims

Two failure modes that compounded into hours lost on the 2026-06-13 YouTube-ingest
cell-lane session. Both are about **prematurely claiming "fixed" when the fix never
actually took effect on the path the user cares about.** They are orthogonal to the
root-cause method — you can do Phase 1 perfectly and still trip these in Phase 4.

---

## Trap 1 — A running process holds the code it imported AT START. Editing after launch = the process still runs the OLD code.

Long-running daemons / workers / ingest loops import their modules **once at process
start**. Editing a `.py` on disk does NOT change the behavior of an already-running
process — it keeps executing the bytecode it imported. This is obvious in the abstract
and *very* easy to forget under time pressure.

The 2026-06-13 sequence, exactly:
1. `23:32:58` — relaunched the ingest wrapper (imported `chunked_transcribe` as-was).
2. `23:33:51` — edited `chunked_transcribe.py` with the actual fix (53s LATER).
3. Watched the live run for ~6 min: still `+0` finalized → concluded "the fix didn't
   work, there must be a deeper bug." **Wrong.** The process at pid X started *before*
   the edit, so it never loaded the fix. I was testing the old code and theorizing about
   a phantom.

**The rule:** before you judge whether a fix worked against a *live process*, prove the
process is running the NEW code. Cheap checks:
- Compare the **process start time** to the **file mtime** of every file you edited:
  `ps -o lstart= -p <pid>` vs `stat -f '%Sm' <edited-file>`. If the file is newer than
  the process, the process has the old code — restart it before drawing ANY conclusion.
- After restarting, re-confirm: the new pid's `lstart` is now *after* every edit.
- (Same family as the Phase-0 "daemon start time vs file mtime — stale processes run old
  code" rule, but it bites just as hard mid-Phase-4 right after you edit the fix.)

A green isolated test/e2e of the fixed code + a flat live counter is the tell: **the
isolated run loaded the new code from disk; the live daemon didn't.** Don't reconcile
that contradiction by inventing a deeper bug — reconcile it by checking what the live
process actually loaded.

---

## Trap 2 — One symptom, several independent root causes stacked in series. Each fix only EXPOSES the next layer; "fixed" is not earned until the WHOLE chain produces the user-visible result.

The user-visible symptom was a single thing: "nothing finalizes into a transcript."
It had at least three independent causes, each masking the next:

1. **`--throttled-rate 100K`** aborted legit slow downloads on a ~50–100 KB/s hotspot
   (downloads churned as `.part`, never completed). Fixed → downloads now complete.
2. **`transcribe_chunked` probed video duration via the REMOTE URL** (with cookies but
   NOT the egress proxy) → on a bot-gated IP the probe returned `''` → `ChunkError`
   killed the whole video even though the audio was already on disk. Fixed (probe the
   LOCAL file) → one video transcribed end-to-end in isolation.
3. **The completion counter still read +0** — and the FIRST instinct was "there must
   be a SECOND duration probe in the production path (`deployment.py`'s pooled
   transcriber) that my layer-2 fix didn't touch." **That theory was WRONG, and
   chasing it was its own lesson (see the correction below).**

**🔴 CORRECTION (2026-06-14, fresh-eyes session): the "layer 3 = deployment.py" theory
was a MISDIAGNOSIS, and the real cause of the flat counter was Trap 1 (thrashing /
stale relaunches), not a third code bug.** When the fresh session actually *ran the
real live path* (`src.ingest --run-slug phase7-full` → `acquire_pipeline.run`) with a
tiny `--limit`, it transcribed a real video end-to-end on the first try. Findings:
   - **`deployment.py` is NOT on the YouTube-ingest path at all.** It's the
     Dropbox/local-file pipeline; its `_run_file_pipeline` operates on
     already-downloaded LOCAL audio (`vr["url"] = str(audio_path)`). The Phase-7
     YouTube run goes `src.ingest` → `acquire_pipeline` (acquire-ahead, proxy passed
     via `_acquire_unit`, transcribe via `transcribe_local_unit` on the local file).
     The "separate probe+download path that never got the fix" **did not exist** on
     the live path. Fingering it from a *code read alone* — without running the live
     path — was the error.
   - **The flat overnight counter was Trap 1, compounded.** The run was relaunched
     ~4× within 25 min (23:13 / 23:32 / 23:38 …); the takeout parse + dedupe alone
     eats ~75s before the first ~60s acquire even starts, so every relaunch was killed
     before a single video could finalize. +0 was self-inflicted thrashing, not a
     finalization bug.
   - **The one REAL remaining bug** the live run surfaced was subtler: a slow/metered
     cell-lane download can fail in TWO opposite ways. The initial "fix" (`--no-part`)
     removed the `.part → final` rename race, but it created a worse silent-truncation
     mode: an interrupted download left a bare `source.m4a` whose header claimed the
     full duration while the audio data ended early, and ASR returned an empty transcript
     that masqueraded as `no_speech`. The final fix is **keep staged/resumable downloads
     (`--continue`, default `.part`) AND full decode-validate the finished file before
     accepting it**; a truncated/corrupt download must raise and retry, not become a
     0-char manifest success.

**The meta-lesson of the correction:** when a fix is correct in isolation but the live
symptom persists, the temptation is to invent a "deeper version of the same bug in a
nearby file." **Resist it. Run the ACTUAL live entry point with a tiny limit and full
output FIRST** — instrument before theorizing. A code-read traced me to a plausible-but-
wrong module (`deployment.py`); a 3-minute `--limit 3` live run showed the path works
and revealed the true (different, smaller) bug. The original Trap-2 *principle below*
(grep for other call sites; "fixed" only when the user-visible signal moves) is still
right — but its worked example here was itself a misdiagnosis, which is exactly why
"observe the real path" outranks "reason about the code."

**Each EARLIER fix (layers 1-2) was real and correct — and each only revealed the
symptom had another cause.** The mistake was declaring "fixed / it's working" after
layers 1 and 2 because *a* probe of progress (bytes moving; an isolated e2e) looked
good, when the **user-visible completion signal never moved** — AND then mis-attributing
the still-flat counter to a phantom third code layer instead of running the live path.

The rules:
- **"Fixed" is earned only when the END-TO-END user-visible result is observed on the
  REAL path** — here, the durable completion counter (`individual/*.txt` / manifest
  `done`) rising on the live run. An isolated unit/e2e proving one layer works is
  necessary but NOT sufficient when there are multiple code paths to the same outcome.
- **Before claiming a layer's fix resolved the symptom, grep for OTHER call sites of the
  same fragile operation.** The duration probe existed in TWO places
  (`chunked_transcribe.transcribe_chunked` AND `deployment.py`'s pooled transcriber);
  fixing one and asserting "done" was the error. `grep -rn '<the fragile call>' src/`
  *first* — fixing one of N copies of a bug is a half-fix that reads as a whole fix.
- **When a fix is correct in isolation but the live symptom persists, the next move is
  NOT "there must be a deeper version of the same bug in this file" — it's "trace the
  REAL production path end to end and find which DIFFERENT code path the live run takes."**
  The production orchestrator often uses a different entry point than the function you
  fixed (pooled wrapper vs direct call, fallback branch vs happy path).
- **Say the honest in-between state to the user, every time:** "downloads complete now,
  but transcripts still aren't finalizing — there's another layer" — NOT "fixed, it's
  working." Serial premature "fixed" claims (it happened ~4 times that session, each
  rightly called out) destroy trust faster than the slow grind itself. The completion
  counter moving is the only thing that licenses the word "working."

---

## Meta-rule

When you've fixed a real bug, the question is never "is this fix correct?" (it can be,
and still leave the symptom). The question is **"did the thing the user asked for now
happen, observed on the real path?"** If you can't point at the user-visible completion
signal moving, you are staged, not done — and you must say so.

---

## Trap 3 — A safeguard that EXISTS and is TESTED but is not wired into the live path (2026-06-14)

The mirror image of "fixing the wrong code path": a protection you (or a past session)
*built and unit-tested* never actually runs where it matters, so it silently protects
nothing. Symptom this session: a 3-hour lofi-music playlist was downloaded *whole* and
chunked into 23 pieces on a metered cell lane — exactly what the **no-speech gate**
(`caption_probe.py`: metadata-probe → 90s-confirm → skip the multi-hour download) was
built to prevent. The gate was fully implemented and had passing tests. The bug:

> `grep -rln 'run_no_speech_gate\|caption_probe' src/` showed it referenced **only in
> `transcribe.py`** (the inline path) and **never in `acquire_pipeline.py`** — the
> acquire-ahead producer that the live Phase-7 run actually uses. The producer downloads
> the whole file *before* anything could gate it. Built ≠ wired.

**The rule — verify a safeguard is ON THE PATH, not just present in the repo.** "We built
X to handle this" is a claim to *test against the live entry point*, not to assume. When a
protection appears to have not fired:
1. `grep` for the safeguard's function across `src/` and note **which modules import it**.
2. Trace the **live entry point** (here `src.ingest` → `acquire_pipeline.run`) and confirm
   the safeguard is called on THAT path — not only on a sibling/inline path with the same
   purpose. A pipeline that has both an "inline" and an "acquire-ahead/pooled" path will
   often have the guard on only one.
3. If it's missing, that's the fix (wire it in, RED-first with the offending input as the
   fixture), not a re-implementation. Don't conclude "the gate is broken" — it was never
   invoked.

This is the same family as Trap 2's "fixed the wrong code path": **the existence of code
is not evidence it runs on the path the user cares about.** Tested-in-isolation +
not-wired-to-live is indistinguishable from absent, from the user's seat.

---

## Trap 4 — A silent fallback that degrades quality is a fake-green; default to fail-loud (2026-06-14)

A wrapper/service with a "primary → fallback on failure" shape can silently hand back a
*lower-quality or empty* result that the caller banks as success. Here the shared
`parakeet-transcribe.sh` wrapper fell back to local **Whisper** whenever the Parakeet
service health-check failed — but the user's standing directive is **Parakeet-only**; a silent
Whisper downgrade is a quality fake-green (and, with a degraded model, an empty transcript
that looks like a real "no speech" terminal). It hadn't actually fired this session (every
manifest entry was `ace-ai-parakeet`), but the *capability to silently degrade* is the
liability.

**The rule:** an automatic fallback that changes the quality/engine of a result must be
**opt-in (default OFF) and fail LOUD** when the primary is unavailable, so the caller
retries the primary rather than banking the degraded output. Fix shape used here: gate the
fallback behind an explicit env flag (`PARAKEET_ALLOW_WHISPER_FALLBACK=1`), and by default
emit a distinct loud error (`parakeet_unavailable`, exit non-zero) instead of a
plausible-looking transcript. Prove it: point the wrapper at a dead service URL and confirm
it returns the loud error, NOT a fallback transcript. When auditing any "primary/fallback"
component, ask: *if the primary is down, does the caller get a clearly-marked failure, or a
silently-worse success?* The latter is the bug.

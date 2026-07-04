# Classify on the Full Evidence, Not the First Matching Keyword

Two real misdiagnoses from one session (2026-06-10), both caught by the user,
both the same root error: **asserting a cause from a single matched token
instead of reading the whole signal.** This is the cheapest class of bug to
avoid and the most embarrassing to ship.

## Case 1 — "57% of failures are dead videos" (WRONG: they were rate-limits)

A batch transcription run had ~2,100 failed items. I bucketed them by matching
the word **`unavailable`** in the error and reported "57% are dead/unavailable
videos — pre-filtering them is a big win."

The user pushed back: *"that can't be right, are you sure it's not just YouTube
rate limiting us?"*

Reading the **full** error string (which I had truncated):

```
ERROR: [youtube] -05v44jLbPM: Video unavailable. This content isn't available,
try again later. Your account has been rate-limited by YouTube for up to an hour.
It is recommended to use `-t sleep` to add a delay between video requests...
```

**84% of the "dead videos" were recoverable rate-limit failures.** The word
`unavailable` appeared, but the *operative* phrase was "rate-limited... try
again later." The misclassification inverted the fix: I was about to build a
"skip these forever" filter for videos that just needed a backoff-and-retry.

**Cost asymmetry that makes this critical:** mislabeling a *transient* failure
as *terminal* abandons a recoverable item permanently; the reverse just costs
one cheap retry. So when a message is ambiguous, **the transient/recoverable
classification must win.**

## Case 2 — "the subagent stubbed because a bare leaf has no agentic loop"

A delegated research task returned a 4-second stub (`api_calls:1`,
`tool_trace:[]`). I confidently diagnosed: "a bare leaf has no agentic-loop
scaffolding, so it treats its plan as the answer."

**Wrong.** The actual cause was already documented in the `subagent-router`
skill's pitfall #0: I passed `toolsets=["web_search","web_extract"]` — those are
TOOL names, not TOOLSET names. The only valid web toolset is `"web"`. The child
got **zero tools**, so it had nothing to call. A one-word config error on my
end, not a harness limitation. The `tool_trace:[]` + `api_calls:1` was the exact
documented tell.

## The rules

1. **Read the WHOLE error/signal before classifying, never the first keyword.**
   Truncated logs are how you miss the operative phrase. If you're bucketing N
   items by a regex, dump the *full unique messages* (`Counter(e[:300] for e in
   errs)`) and read them before naming a cause.

2. **When classifying failures transient-vs-terminal, transient wins ties.**
   A message matching both a dead-link phrase and a rate-limit phrase is
   transient. Encode this in the classifier's check order (transient regex
   first) and TEST it with the verbatim ambiguous string as a regression lock.
   The bare word "unavailable" is not a terminal signal; only specific phrases
   ("private video", "removed", "terminated", "404") are. **This applies to the
   transcribe stage too: a no-speech marker (`stitched transcript was empty`)
   that ALSO carries a `try again later` rate-limit phrase must still be
   transient — check the transient regex first even in the no-speech classifier.**

3. **A subagent's `exit_reason: completed` is not proof it did the work.**
   Verify via `tool_trace` (must be non-empty for any tool-using task) +
   `api_calls` (≥3 for a real research/edit task; ==1 means it answered from
   memory and stopped). A stub looks identical to success in the summary text.

4. **Check the relevant skill's documented pitfalls BEFORE inventing a novel
   root cause.** Case 2's answer was already written down. When a tool/subagent
   misbehaves, `skill_view` the governing skill's pitfalls first — the
   "interesting" hypothesis you reach for is often a known, boring config error.

5. **Believe the user's domain hunch as a hypothesis to test.** In Case 1 the
   user's "isn't it rate-limiting?" was correct and I was wrong; treating it as
   a first-class hypothesis (re-read the full errors) resolved it in one step.

## Update (2026-06-13) — the SAME trap recurred, plus 4 deeper lessons

The same project's re-pass was found wasting its rate-limited budget re-downloading
~38% un-completable items (dead videos + instrumental music) every pass. Fleshing out
the failure taxonomy surfaced lessons beyond "read the full string":

6. **A classifier that EXISTS is not a classifier that's WIRED.** `acquire_errors.py`
   already had `classify_acquire_failure` (transient/terminal) from Case 1's fix, and
   `manifest.should_reattempt` already returned False for `terminal` — but the resume
   loop built its work queue purely from `is_done()==False` and **never called
   `should_reattempt`.** So terminal items were re-queued forever; the terminal verdict
   was computed, stored, and ignored. **When a fix is "classify X as terminal so we skip
   it," grep for the consumer that's supposed to ACT on the verdict and confirm it's on
   the live path — a green classifier unit test proves the label, not the skip.** (Same
   family as coding-guardrails' "a test-only invariant is not enforced.")

7. **A second failure STAGE needs its own classifier, or it records `fail_kind=None`
   and retries forever.** Acquire failures were classified; transcribe-stage failures
   (empty transcript = no-speech music) went through a different code path that recorded
   `fail_kind=None`, which `should_reattempt` treats as retryable. Audit EVERY place that
   records a failure — not just the one you're looking at — for the classification call.

8. **Terminal classification needs POSITIVE evidence; "empty" alone is ambiguous.** An
   empty transcript can be no-speech (terminal) OR ASR-dropped-real-speech (recoverable).
   The codebase already encoded the discriminator in the *message*: `stitched transcript
   was empty` (every chunk measured quiet → terminal no_speech) vs `produced no transcript
   (loud_dropped…)` (loud audio ASR failed on → transient). Use the existing
   positive-evidence marker; don't mark terminal on absence-of-output. On a MIGRATION
   that reclassifies old failures you have no audio to re-probe → default ambiguous-empty
   to TRANSIENT (re-attempt once, classify live with real loudness). Migration script:
   dry-run by default, timestamped backup, atomic write, never run under a live writer.

9. **PROVE the ambiguous bucket empirically before committing the verdict.** 1,804 items
   failed with "Requested format is not available" — ambiguous (could be dead or a
   transient PO-token/client artifact; GH yt-dlp #13058/#16006 say "doesn't mean what it
   says"). Rather than guess, tested 18 random ones LIVE through a working egress lane:
   **18/18 returned full title+duration = alive.** That one cheap probe (a `yt-dlp
   --skip-download --print` loop) turned a risky 1,804-item call into a proven one and
   kept them transient. When a whole bucket's fate is ambiguous AND large, a live
   spot-check of a random sample beats forum reasoning.

10. **The running process is the OLD code until you restart it.** After shipping the
    fix, the live re-pass was still re-queuing terminal items because it had been launched
    before the change. A fix isn't live on a long-running job until you stop it (wait for
    0 procs), migrate state if needed, and relaunch on the new code — then verify the new
    behavior engaged (here: the 235 terminal items were absent from the work queue).

## Adversarial dogfood caught a real transient-wins violation (same session)

Running the classifier against deliberately weird inputs (huge string, shell metachars,
unicode, whitespace, **AND ambiguous combos**) found that `stitched transcript was empty
BUT try again later` classified TERMINAL — violating rule #2 — because the transcribe
classifier checked the no-speech marker before the rate-limit override. Fix: check the
transient regex FIRST in every stage's classifier. The adversarial combo input (a
no-speech marker + a rate-limit phrase in one string) is the discriminating fixture; a
test using only clean single-signal strings passes the broken code.

## Tell-tale signs you're doing this

- You bucketed many items by a single substring and are about to report
  percentages without having read a representative sample of the full strings.
- You reached for a novel/architectural explanation for a tool failure before
  checking the tool's own documented gotchas.
- You're treating a subagent/batch "completed" status as success without looking
  at what it actually did (tool_trace, output file on disk, row counts).
- You "fixed" a classification but never traced the consumer that acts on it to
  the live path (the verdict is computed and then ignored).
- You're about to mark a large ambiguous bucket terminal without a live spot-check
  proving those items really are dead.
- You shipped a fix to a long-running job but never restarted it onto the new code.

# Phase 0: Read the prior investigation before proposing fixes

**Class of trap:** In a repo with a deep investigation history, the "two genuine
defects" you derive from staring at raw forensics/logs are usually **already fixed
or deliberately deprioritized** by prior sessions. Building them duplicates solved
work and chases dead paths — the exact failure SOUL warns about (claude-api-proxy
v2.4→2.5 shipped three fixes for the wrong problem).

This is a Phase-0 step that comes **before** Phase 1 root-cause investigation.

## The rule

Before proposing or building ANY fix in a repo that has existing specs/docs:

1. **Find the status board.** Look for `the AGENTS doc`, `docs/SPEC-*-CONSOLIDATED.md`,
   `STATUS.md`, a fix-status table, or a decision doc. `ls docs/`, `find . -name 'SPEC*'`,
   `git log --oneline -20`. If there are many spec files and no index, that absence
   IS the bug — see "leave an anti-duplication artifact" below.
2. **Read it as source of truth**, not the raw data. The forensics/logs will *look*
   like they show novel bugs; they're usually the same already-root-caused mechanism.
   False-positive "parse failures" are often the model *discussing* the protocol
   (tags in prose/code fences), already handled by a classifier.
3. **`grep src/` for the mechanism** before assuming it's unbuilt. A "fence exemption
   for explanatory prose" may already be a severity classifier. A "JSON repair" may
   already be recovered by an existing normalizer.
4. **Confirm what's actually RUNNING.** On-disk fixes that pass tests are NOT live if
   the daemon booted before the fix landed. Check process start time vs file mtime
   (`ps -p PID -o lstart=` vs `stat -f '%Sm' file`). A stale long-running process is a
   real, easy-to-miss gap — "validate live" falsely passes on disk while the running
   code is old.
5. **Only then** propose work, framed against the status board, not from scratch.

## Measurement can DECLINE a fix — that's a valid outcome

A "data-gated" fix (one whose threshold/parameter must be set empirically) can be
**killed by the measurement**. This is a first-class result, not a failure to deliver.

Worked example (claude-bridge Fix B, 2026-05): hypothesis was "session-file bloat
→ scaffold leak, so rotate bloated sessions." The spec correctly left the rotation
threshold UNSET pending a sampler. When the sampler data arrived:
- Clean healthy sessions ran at *higher* line counts than leaky ones (median 816 vs
  232). Line count did not discriminate leaks.
- The proposed ">800 lines" rotation would cut 51% of healthy sessions to catch 6%
  of leaks — a net loss.
- **Verdict: MEASURED → DECLINED.** Wrote the verdict doc, updated the status board,
  did NOT write the code.

Watch for a cross-era confound: comparing a leak dataset from one time window against
a clean dataset from another (e.g. before vs after a different fix landed) can mislead.
State the eras explicitly; if they don't overlap, say the comparison is weak.

## Leave an anti-duplication artifact

When you discover the duplication trap (or that the repo lacks a status board), the
fix is **documentation that stops the NEXT agent repeating it** — this is a thing
the user specifically values:
- Create/patch `the AGENTS doc` at repo root: a "read this before proposing anything"
  guide with a fix-status table (LIVE / DEPRIORITIZED / MEASURED→DECLINED / open) and
  an explicit anti-duplication rule ("most plausible fixes already exist; read the
  CONSOLIDATED doc first; grep src/ before assuming unbuilt").
- When a fix ships OR a hypothesis is declined, update its row in BOTH the consolidated
  spec AND the the AGENTS doc table, and scan for stale prose elsewhere that now contradicts
  the new status (e.g. a footer still calling a declined fix "open").
- Record genuinely-unrelated anomalies you noticed (e.g. a recurring ~64s `chunks=0`
  timeout cluster) as an appendix with a reopen-recipe, explicitly flagged as NOT part
  of the current fix — so the observation isn't lost but also isn't conflated.

## Subagent boundary for staging fork/upstream reconciliation

When delegating a "merge upstream + re-apply our local patch" task, bound it to
**"verify in a separate git worktree, STOP before touching live main"** (the user's explicit
pattern). The subagent should: detect the real default branch (don't assume main/master),
work in `git worktree add`, re-locate moved anchors (line numbers drift), DETECT if
upstream already fixed it independently (don't double-apply), run tests, and report the
exact FF/merge/PR commands for the human — without pushing or resetting live branches.
A good subagent will disprove its own starting premise via live repro (e.g. "2 of the 3
patches are now superseded upstream; only 1 still needed, here's the live crash proving
it") — that honesty is the goal, not blind re-application.

# Verify a "pending" feature isn't ALREADY LIVE before you build for it

**Class:** the Phase-0 trap, sharpened for *forward* work (not just fixes). Before you build a
watchdog, write a "gate" tracker, schedule a cutover, or perform a "flip" that docs/handoffs say is
**pending**, prove the thing isn't *already in production*. A stale status line ("not yet wired",
"shadow-only", "waiting on the cutover") is a HYPOTHESIS about live state — verify it against the
running system, the call graph, and git, exactly like you'd verify a handed-off diagnosis.

## Why this bites (real session, 2026-06)

A multi-session project's docs said the deterministic scorer cutover was **pending** behind a
"`label_coercion_count == 0` for 5 days" gate. Acting on that, a whole turn went into building a
**no_agent watchdog** that would ping the user when the streak completed and say "now go cut over."
The next turn, on a "green light proceed," a *live Hard-Config edit to two production briefs* was on
the table — until a pre-edit verification showed the cutover had **already landed a week earlier**
(`commit … "x-feed live flip to deterministic engine (the user-approved)"`). The "shadow-only" label on
the session's own fix commit was *also* inaccurate — the fix was reachable from the live path and had
been driving real posts since it landed.

Net: a watchdog built to guard an already-passed gate, a doc that actively misled, and a near-miss
production edit that would have been a confident no-op (or worse, a double-apply). The cost was
entirely avoidable with three cheap checks **before** building.

## The three-check verification triad (run ALL THREE before claiming live/not-live)

Counting files, reading a status board, or trusting a commit's own "shadow-only" message are each
*insufficient alone*. The status board lies (it's stale); a commit message describes intent, not
reachability. Prove live-vs-pending three independent ways:

1. **Call-graph reachability — is the "shadow"/"pending" code actually on the live path?**
   Don't trust a function NAME (`select_shadow` was the *live* selection authority, not shadow) or a
   commit's "shadow-only" claim. Statically trace from the live entry point to the code in question.
   A quick AST probe beats grep for this — build a `func → {names it calls}` map and BFS from the
   live entry:
   ```python
   import ast
   tree = ast.parse(open("scripts/the_module.py").read())
   calls = {}
   for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
       calls[fn.name] = set()
       for c in ast.walk(fn):
           if isinstance(c, ast.Call):
               f = c.func
               calls[fn.name].add(getattr(f, "id", None) or getattr(f, "attr", None))
   # BFS from the LIVE entry point (e.g. the function the cron/prompt actually invokes)
   seen, stack = set(), ["live_entry_function"]
   while stack:
       cur = stack.pop()
       if cur in seen: continue
       seen.add(cur); stack += [c for c in calls.get(cur, ()) if c in calls]
   print("target reachable from live entry:", "suspect_function" in seen)
   ```
   If the "pending" code is reachable from what the cron/prompt/service actually calls, it's **live**,
   whatever the docs or the function name say.

2. **`git merge-base --is-ancestor` — is the commit in the code the live process runs?**
   The crons/services often execute straight from a working tree. Confirm the tree is clean and the
   relevant commit is an ancestor of live HEAD:
   ```bash
   git status --short            # clean tree → HEAD is what runs
   git rev-parse --short HEAD
   git merge-base --is-ancestor <feature-sha> HEAD && echo "IN live HEAD" || echo "NOT in HEAD"
   ```
   "Committed" + "ancestor of HEAD" + "clean tree" + "process runs from this tree" = deployed. (If a
   long-running daemon imported the code at start, also check start-time vs file mtime — see
   `multi-layer-fix-and-stale-process-traps.md`.)

3. **Byte-match re-run on REAL data — does the "would-be" output equal what actually shipped?**
   The decisive empirical proof. Re-run the live engine/selection on today's real input and compare
   its output to what actually posted/shipped. If they're byte-identical (same item set, same order),
   the feature is unquestionably already driving production. This also doubles as the "is a flip even a
   no-op?" check: re-run the pipeline under the *current* setting and under the *proposed* setting on
   the same real pool, and diff the posted set. Identical = the flip changes nothing (already live);
   wildly different = the flip is a real product change, not a rubber-stamp (measure before promoting).

## The cleanup obligation when you find it's already live

Finding a stale "pending" is not "oh well" — fix the things that will mislead the NEXT session, and
do it with the cheap/reversible action first:
- **Correct the stale doc** (strike the moot gate, add a dated CORRECTION with the proof). git-revertible.
- **Pause, don't delete, any watchdog/cron** you built for the now-moot gate — its "GATE MET → go do X"
  message is now actively misleading. `pause` is reversible; you may repurpose the script (e.g. flip it
  to a *regression* alarm on the same signal).
- **Close the tracker task as moot** with the three-way proof in the comment.

## The gate-cross / "is this flip a real change?" measurement (reusable)

When a config flip *is* genuinely pending (e.g. `MODE=shadow → embed`), don't promote on a proxy
metric (mean delta-diff) — compute the **true gate-cross**: re-run the live selection twice over the
real pool (current value vs proposed value injected per-item), and count items that actually cross the
posted↔not-posted boundary. `crossed / |posted-union|`. A near-uniform large delta offset that
compresses under a cap is a **baseline-miscalibration** signature (recalibrate the baseline to the new
distribution's median before promoting), NOT evidence the new signal is good. Package the evaluator as
a re-runnable `scripts/` probe and let a weekly no_agent cron post the decision card only when the
gate passes (silent otherwise — alert hygiene).

## Tripwires that should trigger this check

- Docs/handoff/summary say a feature is "pending / not yet wired / shadow-only / deferred / waiting on
  the cutover," and you're about to build infrastructure that *assumes* that.
- You're about to schedule a "cutover" or perform a "flip" on a load-bearing production surface.
- A function/commit is named or labeled "shadow"/"dry-run"/"staging" but you haven't traced whether it's
  actually off the live path.
- You're building a watchdog/tracker whose whole purpose is to announce "now do X" for an X that might
  already be done.

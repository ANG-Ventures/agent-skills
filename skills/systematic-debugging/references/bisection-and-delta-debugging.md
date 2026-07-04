# Bisection, delta-debugging & the hypothesis-log

Three Phase-1 narrowing techniques the spine names. Reach for these when "what changed" is a *range*
or the failing *input* is large, or when an investigation runs long enough that you'd lose the thread.

## 1. `git bisect` — binary-search the commit that introduced the regression

Use when you have: a **known-good** commit, a **known-bad** commit (often `HEAD`), and a
**deterministic** reproduction. Bisect finds the first bad commit in `log2(N)` steps instead of reading
N diffs.

### Manual
```bash
git bisect start
git bisect bad                 # current commit is broken
git bisect good v1.4.0         # this older commit/tag worked
# git checks out the midpoint; test it, then tell git:
git bisect good   # or: git bisect bad
# repeat until git prints "<sha> is the first bad commit"
git bisect reset               # ALWAYS reset — returns you to where you started
```

### Automated (`git bisect run`) — the high-leverage form
Write a repro script that **exits 0 when the code is good, non-zero when bad**, then let git drive:
```bash
cat > /tmp/repro.sh <<'EOF'
#!/usr/bin/env bash
# build/setup if needed, then the actual check:
pytest tests/test_regression.py::test_thing -q   # exit code IS the verdict
EOF
chmod +x /tmp/repro.sh
git bisect start HEAD <last-known-good-sha>
git bisect run /tmp/repro.sh
git bisect reset
```
Gotchas:
- **Exit code 125** = "skip this commit" (e.g. it won't build) — use it for untestable revisions.
- The repro must be **deterministic**; a flaky test bisects to noise. Stabilize the repro first
  (Phase 1 "reproduce consistently") before bisecting.
- If a build step is needed, put it *inside* the repro script so every candidate rebuilds.
- Bisect over a **clean** tree (stash/commit work-in-progress first).

## 2. Delta-debugging / input minimization — shrink the INPUT, not the code

When the code surface is fine but the **failing input** is huge (a 5000-line config, a giant payload,
a long event sequence), minimize it to the smallest input that still fails. The minimal reproduction
usually *points straight at the cause*.

The ddmin idea (Zeller, "Why Programs Fail"):
1. Confirm the full input fails.
2. Cut the input in half. Does a half still fail? If yes, recurse on that half.
3. If neither half fails alone, increase granularity (quarters, eighths…) and try removing one chunk
   at a time, keeping any removal that preserves the failure.
4. Stop when no single remaining chunk can be removed without losing the failure → that's the
   1-minimal failing input.

Practical forms:
- Text/config: bisect lines (`head`/`tail` halves), keep the failing half, repeat.
- Structured input: remove fields/elements one at a time; keep the removal if it still fails.
- A reducer like `creduce`/`shrinkray` automates this for source files; for most fleet cases a
  by-hand halving loop is enough.
- Always re-run the **same** failing check after each cut — the minimization is only valid against a
  stable repro.

A 3-line repro beats a 3000-line one: it removes confounders and makes the root cause obvious.

## 3. The hypothesis-log — an audit trail that survives compaction

In any multi-round investigation, keep a running log so you (a) don't re-test a dead end, (b) don't
lose state when the context compacts, and (c) can actually *count* failed fixes for the Rule of Three
(Phase 4: 3+ failed fixes → question the architecture, don't patch again).

One line per round, appended to a scratch file (`/tmp/<bug>-hypothesis-log.md`):

```
# <bug one-liner> — hypothesis log
R1  hyp: stale cache returns old value   test: clear cache + repro   result: still fails   next: not cache
R2  hyp: race on write lock              test: serialize writes      result: PASSES once, fails under load   next: real but partial
R3  hyp: lock not held across await      test: add lock span test    result: RED→GREEN with span fix         next: FIX, add regression test
```

Why it matters:
- The Rule of Three is only enforceable if failed attempts are **counted** — the log is the counter.
- When you hand the bug to an ephemeral debug subagent (fresh-eyes, after 3 failures), the log is the
  brief: "here's what's already been ruled out — don't repeat it."
- It separates *fact* (test result) from *hypothesis* (what you thought) so a later reader (or you,
  post-compaction) doesn't mistake a guess for a finding.

Keep it terse. It's a trail, not a transcript.

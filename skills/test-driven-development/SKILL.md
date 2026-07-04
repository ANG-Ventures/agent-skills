---
name: test-driven-development
description: "TDD: enforce RED-GREEN-REFACTOR, tests before code."
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, tdd, development, quality, red-green-refactor]
    related_skills: [systematic-debugging, prd-plan, subagent-driven-development, prd-harden]
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

**Always:**
- New features
- Bug fixes
- Refactoring
- Behavior changes

**Exceptions (ask the user first):**
- Throwaway prototypes
- Generated code
- Configuration files

Thinking "skip TDD just this once"? Stop. That's rationalization.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

**No exceptions:**
- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## Red-Green-Refactor Cycle

### RED — Write Failing Test

Write one minimal test showing what should happen.

**Good test:**
```python
def test_retries_failed_operations_3_times():
    attempts = 0
    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception('fail')
        return 'success'

    result = retry_operation(operation)

    assert result == 'success'
    assert attempts == 3
```
Clear name, tests real behavior, one thing.

**Bad test:**
```python
def test_retry_works():
    mock = MagicMock()
    mock.side_effect = [Exception(), Exception(), 'success']
    result = retry_operation(mock)
    assert result == 'success'  # What about retry count? Timing?
```
Vague name, tests mock not real code.

**Requirements:**
- One behavior per test
- Clear descriptive name ("and" in name? Split it)
- Real code, not mocks (unless truly unavoidable)
- Name describes behavior, not implementation

### Verify RED — Watch It Fail

**MANDATORY. Never skip.**

```bash
# Use terminal tool to run the specific test
pytest tests/test_feature.py::test_specific_behavior -v
```

Confirm:
- Test fails (not errors from typos)
- Failure message is expected
- Fails because the feature is missing

**Test passes immediately?** You're testing existing behavior. Fix the test.

**Test errors?** Fix the error, re-run until it fails correctly.

### GREEN — Minimal Code

Write the simplest code to pass the test. Nothing more.

**Good:**
```python
def add(a, b):
    return a + b  # Nothing extra
```

**Bad:**
```python
def add(a, b):
    result = a + b
    logging.info(f"Adding {a} + {b} = {result}")  # Extra!
    return result
```

Don't add features, refactor other code, or "improve" beyond the test.

**Cheating is OK in GREEN:**
- Hardcode return values
- Copy-paste
- Duplicate code
- Skip edge cases

We'll fix it in REFACTOR.

### Verify GREEN — Watch It Pass

**MANDATORY.**

```bash
# Run the specific test
pytest tests/test_feature.py::test_specific_behavior -v

# Then run ALL tests to check for regressions
pytest tests/ -q
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix the code, not the test.

**Other tests fail?** Fix regressions now.

### REFACTOR — Clean Up

After green only:
- Remove duplication
- Improve names
- Extract helpers
- Simplify expressions

Keep tests green throughout. Don't add behavior.

**If tests fail during refactor:** Undo immediately. Take smaller steps.

### Repeat

Next failing test for next behavior. One cycle at a time.

## Why Order Matters

**"I'll write tests after to verify it works"**

Tests written after code pass immediately. Passing immediately proves nothing:
- Might test the wrong thing
- Might test implementation, not behavior
- Might miss edge cases you forgot
- You never saw it catch the bug

Test-first forces you to see the test fail, proving it actually tests something.

**"I already manually tested all the edge cases"**

Manual testing is ad-hoc. You think you tested everything but:
- No record of what you tested
- Can't re-run when code changes
- Easy to forget cases under pressure
- "It worked when I tried it" ≠ comprehensive

Automated tests are systematic. They run the same way every time.

**"Deleting X hours of work is wasteful"**

Sunk cost fallacy. The time is already gone. Your choice now:
- Delete and rewrite with TDD (high confidence)
- Keep it and add tests after (low confidence, likely bugs)

The "waste" is keeping code you can't trust.

**"TDD is dogmatic, being pragmatic means adapting"**

TDD IS pragmatic:
- Finds bugs before commit (faster than debugging after)
- Prevents regressions (tests catch breaks immediately)
- Documents behavior (tests show how to use code)
- Enables refactoring (change freely, tests catch breaks)

"Pragmatic" shortcuts = debugging in production = slower.

**"Tests after achieve the same goals — it's spirit not ritual"**

No. Tests-after answer "What does this do?" Tests-first answer "What should this do?"

Tests-after are biased by your implementation. You test what you built, not what's required. Tests-first force edge case discovery before implementing.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Tests after achieve same goals" | Tests-after = "what does this do?" Tests-first = "what should this do?" |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is technical debt. |
| "Keep as reference, write tests first" | You'll adapt it. That's testing after. Delete means delete. |
| "Need to explore first" | Fine. Throw away exploration, start with TDD. |
| "Test hard = design unclear" | Listen to the test. Hard to test = hard to use. |
| "TDD will slow me down" | TDD faster than debugging. Pragmatic = test-first. |
| "Manual test faster" | Manual doesn't prove edge cases. You'll re-test every change. |
| "Existing code has no tests" | You're improving it. Add tests for the code you touch. |

## Red Flags — STOP and Start Over

If you catch yourself doing any of these, delete the code and restart with TDD:

- Code before test
- Test after implementation
- Test passes immediately on first run
- Can't explain why test failed
- Tests added "later"
- Rationalizing "just this once"
- "I already manually tested it"
- "Tests after achieve the same purpose"
- "Keep as reference" or "adapt existing code"
- "Already spent X hours, deleting is wasteful"
- "TDD is dogmatic, I'm being pragmatic"
- "This is different because..."

**All of these mean: Delete code. Start over with TDD.**

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

Can't check all boxes? You skipped TDD. Start over.

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write the wished-for API. Write the assertion first. Ask the user. |
| Test too complicated | Design too complicated. Simplify the interface. |
| Must mock everything | Code too coupled. Use dependency injection. |
| Test setup huge | Extract helpers. Still complex? Simplify the design. |

## Hermes Agent Integration

### Running Tests

Use the `terminal` tool to run tests at each step:

```python
# RED — verify failure
terminal("pytest tests/test_feature.py::test_name -v")

# GREEN — verify pass
terminal("pytest tests/test_feature.py::test_name -v")

# Full suite — verify no regressions
terminal("pytest tests/ -q")
```

### With delegate_task

When dispatching subagents for implementation, enforce TDD in the goal:

```python
delegate_task(
    goal="Implement [feature] using strict TDD",
    context="""
    Follow test-driven-development skill:
    1. Write failing test FIRST
    2. Run test to verify it fails
    3. Write minimal code to pass
    4. Run test to verify it passes
    5. Refactor if needed
    6. Commit

    Project test command: pytest tests/ -q
    Project structure: [describe relevant files]
    """,
    toolsets=['terminal', 'file']
)
```

### With systematic-debugging

Bug found? Write failing test reproducing it. Follow TDD cycle. The test proves the fix and prevents regression.

Never fix bugs without a test.

## Dispatcher / Multi-Provider Stress Test Pattern

When testing a dispatcher, router, harness, or any layer that fans out to multiple subprocess/network providers (a delegation router, an LLM gateway, a multi-cloud adapter, etc.), per-provider unit tests are necessary but insufficient. The bugs that hurt are in the **dispatch logic itself** — argument validation, error normalization, concurrency, audit trail, contract integrity — and the only way to catch them is a stress test suite that exercises the full integration with real providers.

The pattern, proven on the 2026-05-13 subagent_router v0.1 build:

### Phase structure

Organize the test file into 6 phases. Each phase is a distinct class of failure mode. Tests in each phase are independent and idempotent.

| Phase | What it probes |
| --- | --- |
| **A — Happy path** | Each provider responds correctly to a simple task. Both CLI entry point and library entry point work. |
| **B — Error handling** | Adversarial inputs: unknown provider, bad path, empty input, huge input, **shell metacharacters in user-supplied strings**, disabled provider, malformed config, missing config, bad binary path with fallback, timeout enforcement. |
| **C — Forward-compat / contract rejection** | Args your dispatcher accepts but doesn't yet implement (future-version axes) reject cleanly with a version-hint message. |
| **D — Real complexity** | Real-LLM end-to-end tasks that produce verifiable artifacts — e.g. "write a 2-file Python module and a pytest" → assert the files exist AND `pytest` passes. Same task through each provider so you can compare. |
| **E — Concurrency** | N parallel dispatches via `ThreadPoolExecutor`. Distinct invocation IDs. No collisions in log files. No deadlocks. No race in config load. |
| **F — Contract integrity** | JSON output valid for every case (happy, error, stub). Every dispatch attempt produces exactly one log file. Log JSON has all expected fields. Exit codes are sensible. |

### Required flags on the runner

```bash
python test_dispatcher.py             # full sweep — runs real LLM calls, takes minutes
python test_dispatcher.py --quick     # skip slow real-LLM tests, mechanics only
python test_dispatcher.py --phase B   # focus one phase
```

The `--quick` flag exists because phase D (real LLM tasks) costs real money and takes minutes. Without it, you stop running the suite and regressions creep in.

### Runner skeleton (Python)

A tiny decorator-based runner is enough. Each test is a closure with a single return contract `(ok: bool, notes: str)`:

```python
@dataclass
class TestResult:
    name: str; phase: str; ok: bool; duration: float
    notes: str = ""; error: str | None = None

RESULTS = []

def run_test(name, phase):
    def deco(fn):
        def wrapper():
            t0 = time.time()
            try: ok, notes = fn()
            except Exception:
                RESULTS.append(TestResult(name, phase, False, time.time()-t0,
                                          error=traceback.format_exc()))
                return
            RESULTS.append(TestResult(name, phase, ok, time.time()-t0, notes))
        return wrapper
    return deco
```

Then each phase function defines and immediately invokes its tests — no pytest needed, no discovery magic, runs as a single Python script. Print a summary table at the end.

### The non-obvious rules

1. **Real-LLM tests are mandatory in phase D.** Mocking the provider misses the things that hurt — model-name gotchas (the codex `gpt-5.5` discovery), auth quirks, output format drift, real failure modes. Phase D should produce verifiable artifacts (files on disk, tests that run, exit codes), not just "got a response."

2. **Concurrency tests must use real `ThreadPoolExecutor`.** Sequential calls dressed up as parallel don't catch race conditions in config load, shared log dir collisions, or invocation-ID generation race conditions. Run 3-5 real dispatches simultaneously and assert distinct IDs + distinct log paths.

3. **Test the audit trail itself.** Every code path through your dispatcher (success, validation failure, provider error, timeout, rejection) must produce exactly one log entry. Write a phase F test that calls dispatch() five different ways and asserts five log files exist. This catches the "early-return paths skip logging" bug — common, silently invisible, very painful when debugging production.

4. **Test shell-injection safety with real shell-meta strings.** Phase B5 should pass `$(echo PWNED)`, backticks, `; rm -rf …` (recursive-delete-from-root), `&&` to your dispatcher's user-input path. If your dispatcher uses `subprocess.run(cmd_list, ...)` with a list argument it's safe by construction — but the test proves it AND demonstrates the safety so future-you doesn't refactor to a shell-interpolated string by accident.

5. **Test forward-compat rejection.** If your dispatch contract accepts args for a future phase (host axis, agent axis, snapshot mode — whatever your roadmap says) with sentinel defaults, every non-sentinel value must reject cleanly with a message that names the future version. This freezes the contract: extending it later is a change, not a regression.

6. **Test timeout enforcement.** Set a 2-second timeout, send a task that should take 30 seconds, assert the timeout fires at ~2s with the right exit code (124 on Unix). Cheap, catches all kinds of subprocess-handling regressions.

7. **Bugs found by the test suite go into the suite.** If you find a bug during stress testing, write the test that catches it BEFORE writing the fix. Then you have a regression lock on that specific case.

### When to reach for this pattern

- Any dispatcher / router / fan-out layer over multiple providers
- Any harness wrapper (LLM CLIs, container runners, RPC clients)
- Any code where "failed silently" is a realistic failure mode
- Any code where concurrency, auth, timeouts, and bad input all need to compose correctly

Not for: pure function libraries (regular TDD is enough), single-file scripts, throwaway prototypes.

### Real-world artifact

Working example: `~/.hermes/scripts/test_delegate.py` — 29 probes across all 6 phases, real-LLM tests included, found 2 bugs in v0.1 (raw YAML errors leaking through, rejection paths skipping logs). All fixed before merge.

## Testing Anti-Patterns

- **Testing mock behavior instead of real behavior** — mocks should verify interactions, not replace the system under test
- **Testing implementation details** — test behavior/results, not internal method calls
- **Happy path only** — always test edge cases, errors, and boundaries
- **Brittle tests** — tests should verify behavior, not structure; refactoring shouldn't break them
- **Undersized fixtures for ratio/threshold guards** — see below; the single most common cause of "my new guardrail tests fail spuriously on first run."

## Ratio / Threshold Guards Need Realistically-Sized Fixtures

When the code under test enforces a **proportional or absolute floor** — "refuse if matched/total ≥ 90%", "block if count ≥ 200", rate caps, mass-operation detectors, percentage-based circuit breakers — a fake-client / in-memory store seeded with **only the matching rows** silently violates the guard's precondition. If you seed 5 matches and nothing else, the store *is* 5 rows, so matched/total = 5/5 = 100% and the mass-floor fires **before** the path you're actually trying to test (e.g. the dry-run/token mint, the happy execute path).

Symptom from the 2026-06-10 mem0 destructive-tools build: five bulk-operation tests all `KeyError`'d on `out["confirm_token"]` / `out["hint"]` — the response had no token because the dry-run had (correctly) refused as a mass op. The bug was in the **test fixtures**, not the code; the guard was working as designed.

**Rules:**
1. **Seed the denominator, not just the numerator.** Add a `_pad(client, n=60)` helper that seeds unrelated rows so a small filter match is a realistic minority of the store. Match the real-world ratio (the live store was ~321 rows; a 5-row match is ~1.5%, nowhere near the floor).
2. **Make caps/floors config-overridable and override them small in tests** when you want to *exercise* the boundary deliberately. To test "ceiling = 10 blocks 30 matches," set `max_bulk_hard_force: 10` via the test's config injection AND pad the store big enough that 30/total isn't *also* a mass op — otherwise you can't tell which guard fired. Isolate one guard per test.
3. **Test the floor's "no escape hatch" property explicitly:** assert the mass-refusal response contains NO `confirm_token` / NO `force`-accepts-it path. A guard that's supposed to be unconditional must be tested as unconditional, not just "refuses by default."
4. **When a guardrail test fails, first ask "did an *earlier* guard fire?"** before suspecting the code. Ratio guards, scope locks, and velocity caps compose; a test that trips the wrong one looks like a code bug but is a fixture-sizing bug.

## When a New Test Exposes Orthogonal Bugs (RED bleed-through)

A well-written regression test sometimes reveals MORE failures than the one bug you're fixing — adjacent pre-existing bugs that share the same code path or invariant. Example from a 2026-05-13 session: a new round-trip test for a substitution proxy correctly failed for the targeted bug AND surfaced two unrelated pre-existing round-trip gaps (a missing reverse-map entry; a wrong-order reverse rule).

**Wrong moves:**
- Fix all of them in this commit. Bloats the diff, makes review impossible, ships unrelated changes under one PR title, and breaks bisect.
- Delete the bleed-through assertions. Loses the discovery, lets the other bugs hide again.
- Loosen the assertion to only catch the targeted bug. Makes the regression test weaker than the bug it's locking in.

**Right move: skip-with-documentation.** Mark the orthogonal failures as known-pre-existing using your test runner's skip mechanism, with an inline comment naming each bug and the symptom, so future-you can find them by `grep skip` and address each in its own PR.

Example with `node --test`:
```js
const KNOWN_PREEXISTING_FAILURES = new Set(['running inside', 'clawhub.com']);
for (const [find, replace] of FORWARD_MAP) {
  const testOpts = KNOWN_PREEXISTING_FAILURES.has(find)
    ? { skip: 'pre-existing round-trip gap (separate from line-623 bug)' }
    : {};
  test(`round-trip: ${find} → ${replace} → ${find}`, testOpts, () => { /* ... */ });
}
```

With pytest: `pytest.mark.skip(reason="pre-existing — tracked separately")`.

**Pitfalls when implementing skip-with-documentation:**
- `node --test` treats `{ skip: null }` as truthy-options-object and SKIPS the test. Always conditionally construct the options dict (`{}` vs `{ skip: 'reason' }`), never pass `{ skip: null }`.
- The skip reason must name the bug specifically ("reverse map ordering bug for skillhub.example.com") not generically ("known issue"). Future readers need enough to act without re-deriving the analysis.
- Open a follow-up issue or note for each skipped case before merging. A `{skip}` with no tracker becomes silent technical debt.
- The fix-bug commit message should call out the skipped bonus failures and what they are.

This preserves the discovery, keeps the fix-bug PR clean, and means the moment any of the orthogonal bugs gets fixed, deleting its entry from the skip set is the only change needed to lock it in.

## Structural Invariants for Transform Pipelines

When testing a system that does find-replace transforms (proxy substitution layers, route tables, redirect rules, tokenizers, any rule-priority system with overlapping patterns), per-rule round-trip tests catch the obvious failures but miss the *structural* bugs — bugs where each rule is correct in isolation but their interaction is wrong. Always assert these invariants AS TESTS, not just as conventions in comments:

1. **No duplicate replace-targets.** If two forward rules `[A, X]` and `[B, X]` share the same replace value, the reverse pass cannot deterministically undo `X` (it doesn't know whether `X` came from `A` or `B`). Either merge the rules or move the cleanup-style rule to a reverse-only path. The 2026-05-13 v2.8.6 bug shipped because the duplicate-find warning existed but the duplicate-replace warning didn't.
2. **Every bidirectional rule has reverse coverage.** If `[A, B]` is in the forward list and you expect the harness to see `A` back when the model echoes `B`, then `[B, A]` must exist in the reverse map (or the reverse pass must apply the forward rule in reverse). Codify the bidi/one-way split structurally — separate lists are better than a flat list with a missing reverse entry, because the structural test can assert each list's invariant.
3. **Longest-match-first on reverse application.** When two reverse needles overlap (one is a prefix/substring of another), the longer must fire first. Alphabetical doesn't encode this. Insertion-order is brittle (author has to maintain it manually, and `mergePatterns` can break it). The right invariant is: **sort by descending needle-length, use a stable sort to preserve unrelated rule ordering.** Apply this in every reverse-application site, not just the main one. The 2026-05-13 v2.8.8 bug shipped because three different reverse sites had three different ordering policies and only one was correct.
4. **Structural invariants via programmatic test discovery.** Don't enumerate the bad pairs by hand — write a test that discovers all (longer, shorter) overlapping pairs from the rule arrays at test time and asserts each one round-trips. That way a future rule addition that introduces a new overlap is caught automatically without test-file edits.

**Structural test pattern (Node.js, generalizes):**
```js
test('reverse map: every overlapping-prefix pair applies longer-first', () => {
  const overlaps = [];
  for (let i = 0; i < REVERSE_MAP.length; i++) {
    for (let j = 0; j < REVERSE_MAP.length; j++) {
      if (i === j) continue;
      const [a] = REVERSE_MAP[i];
      const [b] = REVERSE_MAP[j];
      if (a.length > b.length && a.includes(b)) overlaps.push({ longer: a, shorter: b });
    }
  }
  for (const { longer } of overlaps) {
    const [, original] = REVERSE_MAP.find(([s]) => s === longer);
    const reversed = applyReverse(`say ${longer} here`);
    assert.ok(reversed.includes(`say ${original} here`), `${longer} → ${original} fails when shorter rule exists`);
  }
});
```

## Executing a Batch of Related Bugs Surfaced by One Audit

When a single audit (regression test suite, code review, security scan) surfaces N related bugs in the same subsystem, do NOT try to fix them all in one PR even if they look adjacent. The 2026-05-13 audit produced four bugs in `claude-api-proxy`; bundling them would have been a 1000+-line diff impossible to review or bisect.

**Pattern:**
1. **Spec all of them upfront**, in one writeup, with for each: hypothesis, diagnostic recipe, fix options (A/B/C with tradeoffs + explicit recommendation), regression test shape, verification steps, effort estimate, risk level.
2. **Hand the spec to the user**, let them pick options per bug and pick the execution order. The user's preferred order is usually ascending effort/risk — small structural fixes first, big-impact behavioral changes last, so the test-suite expansion compounds before tackling the hardest one.
3. **Execute strictly sequentially**, one PR per bug. Each PR: branch from current master → write regression test (RED) → implement fix (GREEN) → wire into npm test → full suite passes → restart service if relevant → live probe verifies → commit → push → PR → auto-merge (per the user's PR policy for repos we control) → pull master → next bug.
4. **Carry forward state between PRs.** Each new PR's commit message references the audit + the prior PRs in the chain. If an earlier PR's `KNOWN_PREEXISTING_FAILURES` skip set covered a bug being fixed in a later PR, remove that skip entry in the later PR (don't leave dangling).
5. **Final live verification** uses one probe that exercises ALL the fixed bugs together. If the earliest fix regressed under load with the latest fix, this catches it.

Why not parallel branches? Conflicts on shared files (package.json test list, version, the rule arrays themselves) are guaranteed and resolving them defeats the point of separate PRs. Sequential is slower wall-clock but predictable and bisectable.

## Live Provider Regression Tests

When a bug only appears against a live provider/CDN/API, keep the main regression offline first, then add a gated live canary for the provider-specific invariant.

- Make live tests opt-in via an explicit env flag and use the cheapest model/plan path by default.
- Match the real wire shape exactly: if the body says `stream: true`, the test client should also send streaming-compatible headers such as `Accept: text/event-stream`.
- Assert provider-visible behavior, not just status codes. Example: for cache behavior, check first-call `cache_creation_*` and second identical-call `cache_read_*` usage counters.
- Keep live fixtures deterministic; if request 2 is supposed to hit a cache written by request 1, every cacheable byte must be stable.
- Pair live canaries with mock-upstream assertions for the local root cause, such as verifying a proxy strips hop-by-hop headers before forwarding.

## Dormant Live Paths Need Synthetic Parity Tests

A live gauntlet can prove only the paths the current harness actually exercises. If investigation shows the live client drops or normalizes a protocol feature before the next request (example: Hermes emits upstream `thinking_delta` SSE but does not echo `thinking` / `redacted_thinking` blocks back into `messages[].content[]`), do **not** claim that the preservation code is live-tested.

Turn the caveat into an executable synthetic parity test:

1. Prove the live validation gap with captures/logs (`thinking_delta` exists in SSE; no `type: thinking` blocks in outbound history).
2. Build a fixture that injects the dormant protocol shape directly at the pipeline boundary.
3. Assert two things simultaneously: the sacred block is byte/semantic-identical after masking/unmasking, and neighboring ordinary text still flows through the transform. This catches both over-scrubbing and over-masking.
4. Include hostile payload structure inside the sacred block (braces, escaped quotes, backslashes, substitution-target strings) so string-aware scans are proven.
5. Document why the synthetic test exists in the class-level gauntlet/docs, so future agents do not delete it as "not matching live Hermes behavior."

This is still TDD: the test defines required behavior for clients that do exercise the path (real Claude Code/OpenClaw), even if the current harness cannot naturally trigger it.

## Further reading (load when relevant)

- **`references/guard-not-exercised-by-test-layer.md`** — When testing a single
  guard/branch buried inside a pipeline that has earlier gates (over-cap, auth,
  early returns). Covers the "green with AND without the fix" trap (an
  end-to-end test that can't reach the guard so it proves nothing), the rule to
  **delete the fix and re-run after GREEN** to confirm the red is caused by
  *your* guard's absence, dropping to a unit test at the guard's own function,
  and the companion `git checkout <file>` trap that silently reverts an
  *uncommitted* fix mid-experiment.
- **`references/pipeline-aware-testing.md`** — When adding a new transform to
  an existing multi-layer pipeline (proxies, middleware chains, build/test
  pipelines), test assertions on raw fixture values break in non-obvious
  ways because prior transforms mutate inputs before reaching your code.
  Load this before authoring tests that assert on the integrated pipeline
  output, especially when you also need to update existing tests whose
  assertions covered the *old* pipeline output.
- **`references/fake-upstream-retry-harness.md`** — When testing a retry /
  backoff / dispatch wrapper for a Node HTTP proxy or gateway via an injected
  `requestImpl` (fake-upstream) seam. Documents the two footguns that deadlock
  or hang `node --test` (overriding `.destroy` / reading native `.destroyed`;
  computing `attempt` in an async `.then` instead of synchronously) plus the
  the keep-alive `server.close()` hang and the standalone-vs-runner bisect.
- **`references/test-isolation-frozen-state-leaks.md`** — When a suite passes
  in isolation and with fixed order but fails ~1-in-N full random-order runs
  (order-dependent flakiness). Covers the `object.__setattr__` on a frozen
  dataclass bypassing monkeypatch teardown trap, the autouse snapshot/restore
  conftest fixture that fixes it with zero call-site churn, the two-test
  leak-probe pattern to PROVE the isolation actually engages (and why the probe
  must live under `tests/`), and the 5×-consecutive-green bar for claiming a
  flakiness fix.

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without the user's explicit permission.

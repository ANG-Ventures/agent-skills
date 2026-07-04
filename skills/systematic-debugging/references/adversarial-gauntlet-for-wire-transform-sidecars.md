# Adversarial Gauntlet for Wire-Transform Sidecars

When you've shipped multiple non-trivial fixes to a long-running wire-transform sidecar (proxy, bridge, gateway adapter), unit and parity tests catch *individual* regressions but miss *interactions* between fixes. The gauntlet is a standing adversarial test suite that exercises every shipped fix under hostile real traffic.

This is a *methodology* reference, not a step-by-step recipe. The recipe lives in each project's `GAUNTLET.md` (e.g. `~/claude-api-proxy/GAUNTLET.md`).

## When this applies

- You own a long-running sidecar (HTTP proxy, OAuth bridge, streaming middleware) that touches every byte of LLM-shaped traffic.
- You've shipped 5+ fixes in a short period (days or a sprint), each with a regression test.
- You want confidence that the fixes don't *interact* badly under traffic patterns no individual test exercised.
- Pure unit/parity tests use synthetic fixtures; you need the real upstream to surface emergent bugs.
- You've discovered at least one bug class that recurs (e.g. `BOUNDARY_SPANNING_OPERATIONS` in `claude-api-proxy/BUGS.md`) and want a standing probe per class.

## Core principle

Each gauntlet challenge is a **prompt or live probe → specific code path → documented PR fix → regression test file**. Four fields, every challenge. If you can't fill all four, it's not a gauntlet challenge yet — either the code path isn't important enough or the fix isn't documented.

## Probe integrity — a probe that lies about its own results is worse than no probe

Before you trust ANY leak/failure count an adversarial probe reports, audit the probe itself. Two silent-failure modes recur and both produce **false confidence in either direction**:

1. **Mislabeled expected-bound results.** If your probe classifies vectors into "cardinal leak" vs "documented bounded gap", every vector that hits a KNOWN bound must carry the `bounded` flag. A bounded-gap input with the flag omitted gets reported as a brand-new cardinal leak — you waste a cycle "discovering" a gap the suite already documents (e.g. word-char-adjacent brand like `OpenClawFoo`/`OpenClaws` passing through is the documented threat-model boundary, NOT a new bug). Cross-check every flagged leak against the existing `BOUNDED` tests before treating it as new.

2. **Silent no-op vectors.** A vector that depends on a value the probe extracted by a shortcut (regex-scraping a constant out of source, env lookup, etc.) becomes a **no-op that still counts as "ok"** when the extraction returns `null`/empty — the attack never actually ran but the probe reports success. Example this bit: `NOSCRUB_OPEN/CLOSE` are imported from another module (`require('./convert')`), not string literals in `claude.js`, so scraping them out of `claude.js` source returned `null` and the entire NOSCRUB-straddle vector silently did nothing. **Assert non-null on every extracted dependency and fail loudly (or skip-with-a-visible-warning) if it's missing** — never let a missing dependency degrade to a passing no-op.

Rule of thumb: a probe's "✅ N ok" line is only trustworthy if (a) every bounded vector is flagged bounded, and (b) every vector provably executed its intended code path. Make the probe fail closed, not open.

## Anatomy of a gauntlet challenge

The minimum format that makes a challenge useful months later:

```markdown
## Challenge N — <Plain English class name>

**What it tests:** One paragraph. The bug class, not the symptom.

**Code paths exercised:**
- `funcName` (proxy.js:LINE)
- `helperName` (vX.Y.Z addition)

**Documented fix:** PR #N (vX.Y.Z)
**Regression test:** `test/parity/vX.Y.Z-name.test.js`

**Prompt:** (or **Live probe:** for shell-level testing)
> Plain English instruction OR exact bash/curl

**Success looks like:**
- Observable A (e.g. specific `/health` field state)
- Observable B (e.g. specific log line shape)
- NOT 'should work' — observable, post-hoc verifiable
```

The "success looks like" section is the most-violated part. "Should respond correctly" is not a success criterion. "HTTP 400 with body containing `code: profile_mismatch`" is.

## Stacking strategy

- **Single challenges** verify one code path holds under hostile input.
- **Stacked challenges (2+3, 3+4)** verify that two or more fixes coexist when the same request triggers both code paths.
- **The "lethal cocktail" (all challenges in one prompt)** is the hardest test. Latent inter-fix bugs that no single or paired challenge reaches surface here.

If a challenge passes alone but the cocktail fails, the bug is in the *interaction*, not the individual fix.

## What to instrument before running

1. **Body capture on**: every request and response written to a capture dir, byte-replayable. For `claude-api-proxy`: `captureBodies: true`, `captureDir: /tmp/proxy-capture/`. Disk cost is real (~200 KB per request) — plan to disable after the round.
2. **Health endpoint with profile/error counters**: `/health.profiles.errors.{mismatches, ambiguous, noMatchRejected}` should be probeable per round. If your sidecar lacks structured error counters in `/health`, add them before running the gauntlet — otherwise pass/fail attribution is guesswork.
3. **launchd/systemd restart counter visible**: `launchctl print … | grep 'runs ='` (macOS) or `systemctl show -p NRestarts` (linux). A passing `/health` between crash-loop restarts is a false positive that has burned this fleet before.
4. **Telegram (or equivalent) alert path with rate limiting**: Hard-fails should fire alerts but not spam. Verify alert rate-limit signature collapse before testing — one of the gauntlet challenges WILL trigger it intentionally.

## After-action checklist (every round)

- `/health.requestsServed` matches expectation (no silent drops).
- `/health.profiles.errors` is zero unless a hard-fail challenge was exercised.
- No `uncaughtException`, `SyntaxError`, or `EADDRINUSE` in log since the last version-banner marker.
- launchd `runs = 1` (or `NRestarts = N` matching pre-round value).
- Captures archived or deleted per disk policy.
- If anything failed: capture `*-in-raw.json`, write `test/parity/vX.Y.Z-*.test.js`, fix.
- If a code path now has a regression test, link it back into the gauntlet doc.

## Limitation: dormant defensive code

Critical for honesty: not all defensive code in the sidecar is reachable from every harness. Discovered while running Challenge 3 (thinking-block sanctity) on `claude-api-proxy` v2.10.4 via Hermes:

- The proxy has `maskThinkingBlocks` / `unmaskThinkingBlocks` to preserve `thinking` content blocks byte-identically across the wire (Anthropic 400s on the next turn if any byte differs in a thinking block echoed in `messages[]`).
- Hermes does NOT echo thinking blocks back into `messages[].content[]` — it retains only final visible text. Verified by grepping every `*-in-raw.json` capture for `"type":"thinking"` → zero matches.
- Therefore the mask/unmask code is **dormant on the Hermes path**. It might be on the hot path for real Claude Code or for OpenClaw in tool-loop contexts, but the gauntlet driven from Hermes does not exercise it.

**Honesty rule:** when claiming a challenge "passed," distinguish between:

- **Actively verified**: the code path fired during the round and produced the expected behavior (e.g. `profile_mismatch` returned HTTP 400).
- **Indirectly verified**: the absence of failures consistent with the code path being broken (e.g. 49 sequential turns succeeded, so *nothing* in the request pipeline crashed).
- **Unreachable**: the code path is dormant on the harness driving the gauntlet. The challenge proves nothing about that code path; it can only be exercised from a different harness.

Lying about which category a "pass" falls into is worse than admitting "I can't test this from here." The user can decide whether to spin up a different harness or accept the gap.

## Rule for adding new challenges

When a new bug class is discovered (per the `BOUNDARY_SPANNING_OPERATIONS` pattern), add a Challenge N+1. Each new entry needs the four required fields (what / code paths / fix / regression test) plus a prompt and observable success criteria.

The gauntlet grows. It never shrinks. Removing a challenge means deleting a regression test, which means the bug class can come back without anyone noticing.

## Worked example

`~/claude-api-proxy/GAUNTLET.md` (v2.10.4, May 2026): 7 challenges covering tool-call avalanche, backtick minefield, thinking-block sanctity, massive system prompt, identity-marker collision, recursive self-reference, and a lethal cocktail. Each maps to specific PRs (#5, #7, #8, #10, #11, #12, #14, #15, #17) and regression test files in `test/parity/`. Used live during a single session to harden v2.9.0 → v2.10.4 with `captureBodies` instrumentation feeding byte-replayable failure cases back into new regression tests.

## Backfilling regression tests for dormant code paths

The May 2026 follow-up (PR #18, `test/parity/v2.10.5-thinking-block-byte-identity.test.js`) addressed the dormant-code-path limitation directly: even when the live harness can't reach a code path, you can still pin the path with deterministic unit tests that exercise the transform functions in isolation.

**Pattern: byte-identity test for opaque blocks (thinking / redacted_thinking / signature-bearing content).**

The goal is to assert that bytes inside an opaque-typed block are NOT touched by ANY transform in the pipeline, regardless of what other transforms run on surrounding content. The test:

1. Constructs an assistant message with a `thinking` block containing every substitution-trigger string the proxy normally rewrites (`OpenClaw`, `openclaw`, `Prometheus`, `HEARTBEAT_OK`, `running inside`, etc.) plus brace/quote-heavy JSON-like content.
2. Wraps it in a realistic `messages[]` array next to a normal text block whose substitution targets SHOULD be transformed.
3. Runs the forward transform (`processBodyDetailed`).
4. Asserts that the `thinking` block's `thinking` field is byte-identical to the input AND the surrounding text block was transformed normally.
5. Repeats for `redacted_thinking` (different field name: `data`, base64-encoded).
6. Repeats for the response reverse path with a synthetic upstream response.

What this catches that live traffic can't: regressions where a future change adds substitution-on-all-strings-in-messages that doesn't respect the `type === 'thinking'` early-return, OR a future protocol change that adds a new opaque content-block type the proxy doesn't yet allow-list.

### Test-spec authoring pitfalls (real failures during PR #18)

First-draft test specs for transform functions fail in characteristic ways. Fix the spec, not the proxy, when these patterns show up:

1. **Wrong pipeline-stage assumption.** `processBodyDetailed` may convert between request shapes (e.g. Anthropic `messages` ↔ Claude-Code `Messages` / `system` array) before substitutions run. Your extractor needs to know which shape the output is in. Probe the function output shape first with a 5-line script before writing assertions.
2. **Reverse function does less than you think.** A response `reverseMap` might only reverse vocabulary substitutions (string-replace), not tool-rename or prop-reverse. Those happen elsewhere in the pipeline (e.g. when assembling the final SSE chunks for the harness). Expecting `thread_id → session_id` in `reverseMap` alone will fail because that rename is a separate function further down. Read the function signature and adjacent calls before assuming what's in scope.
3. **Test fixtures that travel through the transform.** If your assertion error message contains the literal string `OpenClaw`, and the proxy substitutes `OpenClaw → OCPlatform` on bytes leaving the node process (including stderr in some configurations), your test failure prints with substituted text and the diff looks misleading. Construct sensitive literals dynamically (`String.fromCharCode` for ASCII; concatenation for words). See `self-transforming-systems-debugging.md` for the full pattern.
4. **Identity check on an integrated config without disabling stripSystemConfig.** If your test runs the full transform with `stripSystemConfig=true` (the default), system-level test content gets replaced with the Claude Code billing header and your fixture vanishes. Force `stripSystemConfig=false` when probing substitution behavior on messages-level fixtures.

Iterate by writing a 5-line repro script that calls the transform function directly, dumps the output JSON, and lets you eyeball where your fixture went. The script-then-assertion-then-test loop converges in 2-3 iterations; jumping straight to a full test file usually wastes one or two iterations chasing wrong assumptions.

## Anti-patterns

- **Conversational "did the fix work?" probes without instrumentation.** A `/health` 200 between launchd restarts of a crash-looping process looks like success. Always pair with `runs = N` and post-marker log scan.
- **Single-shot "stress test" with no documented mapping.** "I sent a hard prompt and it didn't crash" is not a gauntlet — it's vibes. Each probe must map to a known code path with a known fix, or the round teaches nothing.
- **Removing challenges that "always pass."** They always pass *because* the regression coverage works. Removing them eventually allows the bug back.
- **Claiming a "pass" without distinguishing actively-verified vs unreachable code paths.** See the "Limitation" section.

## Porting a bounded transform between sidecars with different layering

When you port a proven scrub/transform from one sidecar to another (e.g. `claude-bridge`'s variant-regex brand engine → `claude-api-proxy`), the engine is correct but the **boundary semantics are NOT portable** if the two sidecars layer differently. This bit a real port (2026-06-10, `claude-api-proxy` v2.20.0) and is a recurring class.

The bridge wraps its brand variant in `\b…\b` AND ships a *separate* `\bopen[-_]?claw_\w+\b` camouflage regex that owns brand-prefixed tool tokens (`openclaw_search`). The proxy had **no such companion camouflage layer** — its old literal `split/join` brand pass scrubbed those tokens itself. Porting the bridge's `\b…\b` boundary verbatim therefore **regressed** coverage: the trailing `\b` fails before `_` (a word char), so `openclaw_search` started leaking the brand upstream — a leak the proxy did not previously have.

Recognition signature: the ported transform passes its own unit tests and the obvious vectors, but an adversarial probe finds a leak on a token shape (`brand_<suffix>`) that the *old* implementation handled. The give-away is that the source sidecar had a second layer the destination lacks.

The fix is a boundary choice, not a regex rewrite. Decide what the destination's *only* brand layer must own:
- `\b…\b` — correct only when a separate camouflage layer owns `brand_<suffix>` tokens.
- alphanumeric-lookaround `(?<![A-Za-z0-9])…(?![A-Za-z0-9])` — treats `_`/punctuation/space as token boundaries, so `brand_<suffix>` scrubs (matching the old pure `split/join`) while alphanumeric-glued forms (`brandfoo`, `thebrand`) stay literal (the documented bounded gap). Use this when the brand layer is the *only* defense.

Verify the choice empirically before committing: run both candidate regexes over the real traffic shapes (standalone brand, `brand_tool`, plural, embedded, url) and diff. Then prove the port via the adversarial gauntlet (`npm run attack:brand`) — the probe must exercise the `brand_<suffix>` shape specifically, classify word-adjacent forms as BOUNDED (not leaks), and reject lookbehind-availability assumptions (`(?<!…)` needs a modern runtime; check `node --version`).

Pitfall: a probe that flags a `brand` + long-alphanumeric-suffix string (`openclawaaaa…`) as a "leak" is mis-classified — that IS the documented word-adjacent bounded gap, not a real leak. Tag those vectors `bounded` and slice the dumped match short, or a single 40k-char input floods the report.

## Related skills

- `software-development/systematic-debugging` — parent skill (this is a reference under it)
- `software-development/test-driven-development` — TDD discipline applies; each gauntlet failure becomes a regression test
- `software-development/systematic-debugging/references/self-transforming-systems-debugging.md` — sibling reference, covers byte-level inspection techniques for transforms that touch your own test scripts
- `devops/http-sidecar-fleet-deploy` — the deploy half of the loop; gauntlet is the validation half

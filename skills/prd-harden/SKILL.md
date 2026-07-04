---
name: prd-harden
description: "Harden a built feature/system to ship quality before closeout — cover real failure paths with e2e + integration tests, make lint/typecheck a hard gate, add the negative/adversarial/concurrency/idempotency cases unit tests miss. Use on 'harden this', 'add e2e and linting', 'make it production-grade', 'tighten the tests', 'what's left to harden', or after a feature is built-and-passing but before prd-closeout. Test-first (RED before GREEN) even on existing code. Distinct from prd-closeout (the evidence gate that CHECKS hardening) and test-driven-development (the per-unit loop this applies at the feature boundary)."
version: 1.0.0
author: the orchestrator agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [prd, hardening, testing, e2e, linting, quality, adversarial, verification]
    related_skills: [test-driven-development, prd-closeout, prd-review-pipeline, systematic-debugging, requesting-code-review, coding-guardrails, qa]
---

# PRD Harden

> Reference: `references/atomic-idempotency-and-shadow-watch-hardening.md` captures the reusable atomic-claim pattern for watcher/audit/provenance hardening: avoid TOCTOU `exists → append → marker` races, RED-prove concurrent same-run behavior, make runtime dirs env-overridable for hermetic subprocess tests, and avoid self-referential closeout SHA loops.

Turn "it works" into "it's hard to break." This skill is the deliberate hardening pass between a green build and `prd-closeout`. It exists because passing happy-path unit tests is the *floor*, not the bar — the bugs that reach the user live in the paths nobody tested: the timeout, the second concurrent run, the empty input, the provider with no key, the re-run that should be idempotent, the lint warning that was actually a real bug.

**Core principle:** every real failure path gets a test that fails first without the guard, then passes with it. Lint and typecheck are gates, not suggestions.

## Position in the lifecycle

This skill's place in the full lifecycle: see `skill_view(name='prd-spec', file_path='references/lifecycle.md')`. For **who owns which concept** in this suite, see the ownership map: `skill_view(name='prd-spec', file_path='references/prd-suite-map.md')`. **Immediately upstream:** `build`. **Immediately downstream:** `prd-closeout` (which *calls* this skill).

- **build** makes the feature work and pass its first tests.
- **prd-harden** (this skill) drives coverage of the failure paths, makes lint/typecheck a hard gate, and adds adversarial/negative/concurrency/idempotency cases.
- **prd-closeout** *calls* this skill (or confirms a current hardening report) and BLOCKs if the real failure paths aren't covered.

This skill **applies `test-driven-development`** at the feature/system boundary: TDD owns the per-unit RED-GREEN-REFACTOR loop; prd-harden owns *which* integration/e2e/negative cases are worth writing and how to make the gates real. Load both.

## How we like to do it (the user's standards)

1. **Test-first even when hardening existing code.** To harden a path, first write the case that **fails without the guard** — break the input, kill the dependency, run it twice. Watch it fail (or watch the missing guard let bad data through). *Then* add/confirm the guard and watch it pass. If you can't make it fail first, you don't yet understand what you're protecting. (This is RED-GREEN applied to an already-built system.)
2. **E2E wherever a real path changed.** A green unit layer over a real integration boundary is not hardened. If the feature touches a real seam — a DB, a subprocess, an HTTP provider, a cron prompt, a file lock, a cache file — there must be a test that exercises *that seam*, not a mock of it. Mocks verify interactions; they do not prove the integration works. (See TDD "Dispatcher / Multi-Provider Stress Test Pattern" and "Dormant Live Paths Need Synthetic Parity Tests".)
3. **Lint + typecheck are part of "finalize," not optional.** Treat warnings as latent bugs until proven cosmetic — the `set-state-in-effect` warning, the unused-var, the `any` escape hatch are how real bugs hide. Wire a single `verify` command (typecheck + lint + unit + e2e) and make it exit non-zero on regression. Keep a **warning baseline** (`--max-warnings N`) so new warnings fail CI even if legacy ones are grandfathered — and ratchet the baseline down over time, never up.
4. **Negative and adversarial cases for every trust boundary.** Empty input, huge input, malformed input, shell metacharacters in user-supplied strings (`$(...)`, backticks, `; rm -rf …` (recursive-delete-from-root), `&&`), missing file, missing key, wrong provider, expired lease, 401/402/404/timeout from upstream. Each should produce a *fast, clear, deterministic* outcome — never a hang, a silent pass, or a 90s fall-through.
   **Vary the INPUT-SHAPE axis, not just the value axis — and audit predicate-reachability per shape.** A bug class that survives the diff-review AND a full unit suite AND a value-axis adversarial battery is an **unreachable predicate for a legitimate input shape**: a detector/router/classifier whose terminal-failure check (errored/dead/down) sits *behind* an early-`continue` on a derived/optional field (a NULL interval, a missing schedule, an unparseable timestamp) silently drops that whole input class from the check. Real catch (2026-06-12): a cron detector gated its FAIL rule behind `if stale_deadline == inf: continue`, so 15 live jobs with a NULL `expected_interval_sec` were blind to error detection — one erroring 136× in a row, zero findings, the exact silent-failure the system existed to catch. All tests used a fixed interval, so the dead path was never exercised; only a closeout ground-truth of a live finding caught it. **Rule: a terminal-failure finding must be evaluated FIRST and made INDEPENDENT of optional/derived fields; only the overdue/staleness check legitimately needs a cadence.** Add a field-presence-matrix probe (for each finding type, build an input with each optional field NULL and assert the finding still fires) + a `SELECT count(*) WHERE <field> IS NULL` on the real registry (a non-zero count on a field that gates a terminal check is a *live* blindspot). Full writeup in `references/post-build-diff-review-solo-builds.md` ("the blind-spot that survives BOTH the diff-review AND the unit suite").
   **For a content classifier/miner with EXCLUSION signatures, the input-shape axis is the same-content-different-FORM trap.** A detector that excises "noise regions" (catalogs, code, boilerplate) by a *structural* signature will miss the **prose form of the same content** — and that gap survives the value-axis battery because every test fixture used the structural form. Real catch (2026-06-12): a scrape-failure miner excised skill/tool-catalog dumps via two structural signatures (an `<available_skills>` marker + runs of `- name:` list-lines), but a catalog written as an **inline sentence** — `"Available skills: scrapling (Cloudflare bypass), firecrawl (403 handling), datadome-evade…"` — hit neither, so it leaked 2 false `datadome` incidents (a tool NAME without a fetch ACTION = a false positive). Synthetic-only (no live-corpus hit yet), but a real latent gap a future real catalog would trip. **Rule: for every exclusion/classification signature, enumerate the FORMS the same content can take — structural (markers, list-lines, fenced blocks, tables) AND prose (an inline sentence that frames itself as the thing and names ≥N members) — and write a fixture per form.** The prose-form fixture is the one your structural signature misses; add a content-density signature for it (e.g. a "listing frame" phrase + ≥3 distinct member tokens in a window → excise) and a *discriminating* regression test that fails when the new signature is reverted, PLUS a paired don't-over-excise test proving a REAL hit in the same family still fires (the false-negative guard for the broader exclusion).
   **A side-effecting watcher (fires a real alert / writes operator state) gets injectable seams + a return value, not a manual dry-run.** Give the function `heartbeat_path`/`state_path`/`sender`/`sleep_fn`/`wake_check`-style params defaulting to prod behavior, and have it RETURN the alert message (a testable signal) so tests pass temp paths + a fake sender + a no-op sleep and never fire a real Discord/Telegram alert or sleep 60s. Prove hermeticity with a state-file-byte-identical-after-run assertion. (Same family as `references/hermetic-test-isolation-side-effecting-functions.md`; the deadman example lives in `references/post-build-diff-review-solo-builds.md`.)
   **Side-effecting functions must be hermetically isolated in tests.** If a test calls a real production function that **writes operator state** (a hash/cursor/cache file under `~/`) or **spawns a real notifier** (Telegram/Discord/`notify.py`/email/webhook) with no isolation, every suite run silently mutates real state and can **fire a real live alert** — a self-inflicted bug that masquerades as "the environment/provider changed." Fix: resolve the module's external paths at CALL time via env (defaults unchanged), add an operator kill-switch checked *before* any write or spawn, and have the test set those env vars to a temp dir before `require`. Prove it with a snapshot-diff: a full `verify` run must leave the real state file byte-identical. Fastest root-cause when alerts appear unexpectedly: `grep -rn "<a magic value from the alert payload>" .` — if it lands on a test fixture, the suite is the culprit. See `references/hermetic-test-isolation-side-effecting-functions.md`.
5. **Concurrency, idempotency, and resumability where the design implies them.** If two runs can overlap, test two real concurrent runs (real `ThreadPoolExecutor`/parallel processes, not sequential-dressed-as-parallel) and assert no lock collision / no double-write / distinct IDs. If a job is meant to be safe to re-run, test that running it twice yields the same state (content-hash, upsert-by-id). If it persists a cursor, test that a mid-run failure resumes correctly.
6. **Don't fix orthogonal bugs in the hardening diff.** A good new test often surfaces *adjacent* pre-existing bugs. Lock them with skip-with-documentation (name the bug + symptom in the skip reason) and address each in its own PR. Keep the hardening diff reviewable and bisectable. (See TDD "When a New Test Exposes Orthogonal Bugs".)
7. **Verify against the original failure conditions, not a synthetic proxy.** "Fixed" means you can no longer reproduce the failure under conditions like how it was found. A module-level repro that doesn't exercise the user-facing path doesn't count.
8. **De-brittle tests that assert on live, drifting state.** A test hardcoding a live row count / corpus size / today's date will go red on its own. Assert structural invariants (`bookmarks + likes === rows`, "> 0", "monotonic") instead of magic numbers. A test that's red for reasons unrelated to the code under test is a broken gate — fix it as part of hardening. **The same brittleness hides under a renamed constant/token, not just live data.** When a value the code defines (a sentinel, alias, brand token, prefix, enum, default) is hardcoded into many *mechanism* tests, renaming it later turns the whole suite red at once — and the fixtures can hide the coupling three ways: (a) the literal, (b) a `String.fromCharCode(...)`/hex byte-encoding (used to dodge a self-transforming layer — see `systematic-debugging`), and (c) a *fixture split at a byte boundary specific to the old token* (e.g. an SSE straddling-needle test that splits `"ocplatform"` as `"oc"`+`"platform"`). A blanket find/replace won't fix (c). The durable fix: **derive the token from its source-of-truth export at runtime** (`const FWD = DEFAULT_REPLACEMENTS.find(([f]) => f === 'brand')[1]`) and compute splits programmatically (`tok.slice(0,2)` + `tok.slice(2)`), so the test tracks any future rename and can never hardcode-rot again. Exception: a test using its *own* self-contained fixture config (not the shipped constant) is already decoupled — leave it. Worked example: retiring an old sentinel for a new one in `claude-api-proxy` broke 15 tests across 8 files; deriving the sentinel from `DEFAULT_REPLACEMENTS`/`DEFAULT_REVERSE_MAP` fixed them durably. Pair this with a **static config-drift lint** (a script that builds the real pipeline and asserts the old token is GONE + the new one is present + no leak) so a re-introduction fails the gate, RED-proven by temporarily reverting the constant.
9. **Run a senior diff-review of the integrated code — on SOLO builds too, not just swarms.** A post-build Opus review of the *integrated diff* (`prd-review-pipeline` §2.8.1) catches a different bug class than tests: cross-module seam/contract mismatches where the producer, consumer, and both their tests share your blind spot. It is **most** valuable on code you wrote solo (you also wrote the tests, so a contract bug is invisible to them) and on **observability/watcher code** (a silent-failure seam bug in the thing that catches silent failures is the worst outcome). Multi-pass the build the same way you multi-pass a spec — expect the Pass-1 fix to introduce a Pass-2 finding. And when a fresh hardening test goes red, suspect the **test** first (impossible scenario, shared-PK fixtures, wrong assertion) before the product. Proven 2026-06-12: 48 green tests, one diff-review → BLOCK with a recovery that announced "recovered" for a live-broken job + a wrapper that manufactured false STUCK alerts. See `references/post-build-diff-review-solo-builds.md`.
10. **An LLM-prompt cron is a real seam — its FIRST scheduled run is the e2e, not your dry-run.** When you wire a new helper/script into a load-bearing agent-driven cron (a brief, digest, triage prompt), running the *helper alone* on real data proves the helper, NOT the agent's orchestration loop around it. The agent can still: post multiple times in one run, fail to merge the helper's output back onto its items, or ship an empty husk. Two guards are mandatory before you call it hardened: **(a) a single-post idempotency guard** — one run = one external post; mark a per-run lock (`/tmp/<job>-posted-<RUN_ID>.lock`) and HARD-stop a second `notify`/post call ("don't repost to improve/correct/add what you missed — a duplicate is a bug"); **(b) an explicit merge-back-by-id step** — "match the helper's `items[].id` back onto your candidates and copy the fields; `ok:true` MUST yield non-null deltas; a run where the helper fired but base scores were used is a BUG." Treat the first real scheduled run as the verification step (manual dry-runs don't exercise it). See `references/llm-cron-orchestration-hardening.md`.
11. **Harden a pure-predicate guard by its WIRING/ORDERING, not by re-testing the predicate — and when the guard's value is "fail FAST, before an expensive/irreversible side effect," lock the ordering with a call-count tripwire.** A small pure validator (a tip/amount/scheme allowlist, a cap check, an auth gate) is trivially unit-coverable on the value axis — and that coverage is the FLOOR, not the hardening. The real risk is a future refactor that moves the check to the wrong place: *after* the browser attach, *after* the cart/network lookup, *after* the irreversible write. A value-axis battery never catches that (the outcome is still "rejected"); only an **ordering property** does. The lock: stub every downstream side-effecting boundary with a **call-count tripwire** and assert each is `== 0` when the guard should have short-circuited — e.g. a non-preset `--tip-cents` on the live path must leave `cart_show`/`mint_token`/`checkout` all uncalled. **RED-prove it by deleting/moving the guard** and watching the tripwire trip (the downstream stub gets reached) — an ordering test you haven't watched fail against the un-guarded code is an assertion, not a proof. Real catch (2026-06-13, fleet-shop tip v0.1.6): the guard fn had a full value+type+set unit suite, but the load-bearing AC was "reject *before any browser work*"; only the tripwire test (cart_show/mint/checkout == 0, RED-proven by removing the early CLI check) actually guarded that. **Two-seam authority corollary:** when the same guard lives at a fast user-facing seam (CLI, for the friendly early reject) AND an authoritative seam (the core function, defense-in-depth before the irreversible step), call ONE shared predicate from both — never duplicate the rule — and test the *fast* seam for ordering and the *authoritative* seam for un-bypassability (a programmatic caller skipping the CLI is still held). Also test the **negative-scope** case: a path that legitimately does NOT touch the guarded resource (e.g. preview never sets a tip) must NOT be gated by the guard, or you've over-broadened it.
12. **A green unit suite proves your CODE agrees with your FIXTURES, not with the real dependency.** When a feature wraps an external binary / API / SDK, the unit tests stub its output — so if the BUILD assumed the wrong contract (wrong response field, a missing required flag, the wrong of two possible backends), the FIXTURES encode that same wrong assumption and the whole suite is green over a broken integration. The only thing that exposes it is a **live GSD walk against the real dependency**. Real catch (2026-06-12, fleet-shop Instacart): a wrapper keyed auth on `authenticated` but the real binary returned `logged_in` (→ *every* live checkout would have falsely aborted at the precheck); three read commands omitted a required `--json` flag (→ the binary pretty-printed text the parser choked on); the live "place order" path launched a *headless* browser the site's anti-bot bounces while the proven backend was a CDP-attach to the real logged-in browser — **none of which any unit test caught, because the fakes returned well-formed JSON through an in-process `page` seam that the real session-open code never ran.** Rule: for every wrapped external dependency, the hardening pass MUST include ≥1 walk that drives the REAL binary/API/seam (not a mock) and asserts on its ACTUAL output shape; "the unit suite is green" is the floor, and the live walk is where the contract bugs hide. The same walk also caught a **wrong-env test runner silently SKIPPING the integration-seam tests** (pytest with no asyncio plugin → "2 skipped" read as a pass while the real code never ran) — give the wrapped feature its own venv with the right plugins + an `asyncio_mode=auto`-style config so the seam tests actually execute.
13. **Observability is a hardening dimension — treat logging as TESTABLE coverage, not decoration.** A failure path you can't *see* fail in production isn't hardened; when it breaks at 3am the logs are your only instrument. So the hardening pass owns logging coverage of the paths it hardens: every important path (user flow, service boundary, background job, **failure path**) must emit a useful, structured, **tested** log — and the test asserts on the *emitted event*, not just that the source line exists. This is the production-observability twin of rule 4 (you wrote the failure test; now prove the failure is *legible* when it fires). The full procedure — the inventory (event · outcome · severity · correlation-id · fields), the success-AND-failure log test pattern, the redaction gate (never log secrets/tokens/PII — for this fleet that's the same `brand-safe`/`SECRET_RE` hygiene the journal + notify use), the stable-event-name-over-interpolated-prose rule, and the "log a loud greppable reason on every silent-degrade" rule that makes the dark-feature trap debuggable — lives in `references/logging-coverage-hardening.md`. **Load it when the feature has real failure paths, a cron/daemon, or any silent-degrade branch.** The cheap tell you skipped this: a degrade/except path that logs *nothing*, so when it fires in prod the root cause takes hours instead of one `grep`.

## The hardening pass — procedure

1. **Map the failure surface.** List every real path the feature touches and every way each can fail. For each, note: is there a test that exercises *this exact path failing*? Build a small gap table (path × failure-mode × covered?).
2. **Rank by blast radius.** Hardest-hitting first: data loss > silent-wrong-output > hang/outage > crash-with-clear-error > cosmetic. Load-bearing prod paths (briefs, crons, anything the user sees daily) rank above internal tooling.
3. **Close each gap test-first.** RED (prove the gap) → GREEN (guard) → REFACTOR. One failure-mode per test, named for the behavior ("survives a hard-failing image mid-OCR-batch and still processes the good media after it").
4. **Make the gate real.** Ensure `verify` runs typecheck + lint(+baseline) + unit + e2e and fails on any regression. If e2e needs a real dependency (key, binary, service), provide a `verify:live` variant and make the offline e2e **hard-fail** (throw, not skip) when the real dependency is *configured but degraded* — silent skips are how the vec0 brute-force demotion hid for days.
5. **Run the full suite, capture exact output.** Not just the new tests — prove no regression across the whole suite. Record `N passed`.
6. **Re-verify against original conditions.** Re-run the real user-facing path (live or dry-run) and confirm the symptom is gone and the new artifacts/guards engage.
7. **Run the GSD verify-walk.** Before declaring the feature hardened, enumerate every acceptance criterion and claimed-done item, walk each on the real path with a concrete check/command, and record the actual evidence. If any row is assertion-only, blocked, skipped, or synthetic-proxy-only, hardening is not done.
8. **Hand to `prd-closeout`** with the evidence: failure-surface table, new test names, `verify` output, live re-verification, and the GSD verify-walk table.

## GSD verify-walk — acceptance criteria to evidence

GSD = **Get Stuff Done**: do the concrete walk that proves every "done" claim before you let the work move to closeout. This is the `coding-guardrails` prove-with-evidence rule applied to PRD hardening: success is real evidence on the real path, not a confident assertion.

1. **Enumerate the claims.** Pull every acceptance criterion from the PRD/build spec, every hardening checklist item, and every "done" claim in the handoff. Put one claim per row; don't collapse multiple behaviors into one vague line.
2. **Name the real path.** For each row, identify the user-facing or production-equivalent path that would prove it: route, CLI, cron, integration seam, persisted artifact, UI flow, or live dependency. If the real path is unavailable, mark the row blocked; don't substitute a toy proxy and call it green.
3. **Choose a concrete evidence check.** Write the command, test, live smoke, log query, artifact inspection, or UI walkthrough that exercises that real path. The check must have an observable pass/fail signal: exit code, assertion, emitted artifact, log line, database row, screenshot, or external post.
4. **Run the check and record actual evidence.** Capture the command/check, exit code, relevant output lines, artifact paths, and timestamps. Quote the evidence you saw; don't paraphrase what should have happened.
5. **Close or reopen.** A row is green only when the evidence matches the criterion. If it is skipped, missing, synthetic-only, or mismatched, reopen hardening and add/fix the test or guard before trying the walk again.

Use this table shape in the hardening handoff:

| Acceptance criterion / claimed-done item | Real path walked | Concrete evidence check | Actual evidence recorded | Status |
|---|---|---|---|---|
| "Retry is idempotent" | real job rerun against the persisted state | `python scripts/job.py --run-id <same-id>` twice + inspect persisted rows | exit 0 both runs; row count unchanged; log shows existing row reused | green |

## Output: hardening report

```markdown
# Hardening Pass — [Feature/System]

**Ran against:** `<git rev-parse HEAD>` (build paths clean: yes/no)   <!-- D11: closeout compares this SHA to verify the report is current; `not a git repo` if untracked -->

## Failure surface (gaps found → closed)
| Real path | Failure mode | Was covered? | Test added | RED proven? |
|---|---|---|---|---|
| OCR batch | one image 404s mid-batch | no | e2e: good media after bad still flows | yes (threw before guard) |
| provider resolve | preferred has no key | no | unit: auto-picks present provider, never null | yes |

## Gates
- `npm run verify`: typecheck + lint (--max-warnings N baseline) + unit + e2e → <exit 0, N passed>
- e2e real-dependency policy: <hard-fail when configured-but-degraded / live variant>

## GSD verify-walk
| Acceptance criterion / claimed-done item | Real path walked | Concrete evidence check | Actual evidence recorded | Status |
|---|---|---|---|---|
| [criterion from PRD/spec/handoff] | [route/CLI/cron/UI/integration seam] | [`verify` / targeted test / live smoke / artifact inspection] | [exit code + output/log/artifact path observed] | [green / blocked / reopened] |

## Negative / adversarial coverage added
- [empty / huge / shell-meta / missing-key / timeout / 402 …]

## Concurrency / idempotency / resumability
- [two real parallel runs → no lock collision; re-run idempotent; cursor resumes]

## Orthogonal bugs found (deferred, not fixed here)
- [skip-with-doc entries + follow-up], or None

## Live re-verification
- [re-ran the original failing path: symptom gone, guard/artifact engaged]

## Remaining hardening debt
- [explicit list], or None
```

## When NOT to over-harden

- Throwaway spikes/prototypes (use `spike` — then throw away and rebuild with TDD).
- Pure stdlib-only helper with no integration boundary — regular unit TDD is enough; don't invent an e2e harness for a pure function.
- A cosmetic warning *proven* cosmetic — grandfather it in the baseline with a comment, don't block forever, but don't let new ones in.

Hardening is proportional to blast radius. A daily cron that posts to the user and bills an API earns the full pass; a dev-only debug page does not.

## Anti-patterns

- **"Tests pass" = done.** Happy-path green is the floor. Did you test the timeout?
- **Mock the seam you're trying to harden.** Mocking the provider/DB/subprocess you're hardening proves nothing about the integration.
- **Silent skip on missing dependency.** A skipped e2e when the real dep is *configured but broken* is a hidden red. Hard-fail instead.
- **A smoke test that resolves `python3`/a tool from `$PATH` can false-SKIP.** A bash heredoc calling bare `python3` may resolve to a *different* interpreter than the one the system actually runs under (e.g. an anaconda/pyenv shadow lacking the dep) — so the smoke prints "[SKIP] X not installed" while X *is* installed in the real env. A misleading skip is an observability bug (it hides whether the gating path works). Fix: probe candidate interpreters/paths for the dep, use the first that HAS it, and **report which one was used** (`[PASS] … [via /usr/bin/python3]`); only SKIP when no candidate has it. Same logic for any `which`-resolved CLI in a verification script.
- **An LLM-behavior test that substring-matches the response false-FAILS.** When hardening a guard whose success is "the model did X, not Y" (e.g. an injection chokepoint: extract the real datum, ignore the planted one), asserting on a *substring* of the prose is wrong — a model that correctly *ignores* an injection often *names* it while explaining why ("the $9999 note is untrusted data, so I report $30"). The substring `9999` then trips a false BREAK. Assert on the **structured/parsed value** the model returned (parse the JSON, check the field), not on whether the attack string appears anywhere in the text. The model mentioning the attack ≠ obeying it; only the extracted value proves obedience.
- **Shell scripts that `export X="$(cmd)"` mask the command's failure (SC2155).** Declare-and-assign in one statement makes the `export` succeed even when `cmd` (a 1Password `op` call, a token fetch) fails — so a broken-auth path looks healthy and fails later/elsewhere. Split declare from assign. Run `skills-shared/hermes-harness/skill-hygiene/scripts/skill-shell-lint.sh` (a shellcheck gate over all skill `*.sh`, severity=error by default) as a hardening gate; it catches this class plus pointless quoted loops (SC2066). The tree is error-clean today — keep it that way.
- **A URL/path CLI arg fed to a browser/subprocess/file-open with no scheme allowlist = SSRF / local-file-read.** A tool that takes a URL and drives a stealth browser will happily fetch `file:///etc/&#8203;passwd` (proven 2026-06-12). Allowlist the scheme/shape at the entry point BEFORE the dangerous call; lock it with a parametrized regression (`file://`/`data:`/`ftp://`/no-host → rejected). See `references/adversarial-cli-library-dogfood.md`.
- **Two same-typed args where one is untrusted and one is a trusted instruction, taken positionally = silent injection on inversion.** A function `f(envelope, task)` (untrusted DATA, trusted instruction) lets a future caller write `f(task, content)` and smuggle scraped content into the instruction slot — a green unit suite won't catch it (the test that found it had the args reversed and still passed). Make the params **keyword-only** (`def f(*, envelope, task)`) so positional inversion is a `TypeError`, not a breach; lock with a regression asserting the positional call raises and sweep call sites to kwargs in the same diff. Cheaper and more durable than a "don't invert these" doc comment. See `references/adversarial-cli-library-dogfood.md` §7.
- **A seam-unit-green + a synthetic-fixture screenshot = the FUNCTION proven, NOT the shipped artifact.** When the deliverable is a rendered document (HTML report, generated page, export), passing unit tests on the render *seam functions* plus a screenshot of a toy fixture do NOT prove the feature is in the thing the user actually opens. The real artifact can have been rendered *before* the feature landed and ship without it (the v4 anchored-citation incident, 2026-06-13: code committed + unit-green + 17-source fixture screenshotted, but the live 153-source report had no anchors and the user caught it by eye). Closeout evidence must be the feature observed on the **real, user-facing output regenerated after the code landed** — add an offline re-render harness that replays the persisted real data through the real render path network-free (seconds, re-runnable) and assert the format on THAT. **The twin failure (render-and-READ): even when the feature IS present and unit-green AND spec-approved, the rendered output can silently DROP a data field — a `_render_single` structured branch built `headline+facts` and dropped the producer `body` verbatim; 155 green tests + a 3-pass Opus spec review + a live smoke all missed it, and a before/after render harness exposed it in 5 seconds of reading (the green tests had *encoded the data-drop as the expected contract*). RULE: when the deliverable is a rendered string/artifact, RENDER the real output for every producer/branch and READ it; the unit suite tests code-vs-fixtures, not output-vs-intent. And when a render bug traces to spec text, check whether that prose CONTRADICTS an AC (it did here — AC said "never drop identity," a later impl-prose paragraph carved out the single path); the AC wins, amend the prose as an as-built note. A config flag that flips which branch is DEFAULT silently promotes a narrow path to load-bearing — re-audit invariants against the newly-default branch. See `references/render-pipeline-and-vacuous-gate-hardening.md` §3–§4.** See `references/render-pipeline-and-vacuous-gate-hardening.md`.
- **A "no X is broken" integrity gate passes VACUOUSLY on "there are no X" — the production-artifact twin of the cert-harness vacuous pass.** A publish gate like `check_integrity(doc)` = "every link resolves to a row" returns ok:True on a doc with ZERO links → it green-lights the exact un-rendered artifact it exists to catch. Any "every A links to a valid B" gate needs a **presence floor**: if the doc HAS the downstream structure it MUST also have the upstream markers, else the render silently no-op'd → FAIL (an explicit `unanchored_sources`-style flag). Keep a scope guard so a legitimately empty doc still passes, and RED-prove by stripping the upstream markers from a known-good artifact while leaving the downstream rows. See `references/render-pipeline-and-vacuous-gate-hardening.md` (and `references/certification-fixture-teeth.md` §2 for the cert-harness version).
- **A green happy-path smoke + a passing spec review = the DESIGN and HAPPY PATH proven, nothing else.** Malformed input, prerequisite-absence (FAIL-vs-SKIP parity), verifier-correctness, and AC completeness are a SEPARATE adversarial-dogfood pass — mandatory for any shipped CLI/library. Self-audit the spec's own ACs (`grep -nE 'AC-[A-Z0-9-]+'` → point each at the artifact that satisfies it) as a closeout step, not on the user's prompt.
- **Warning baseline ratchets up.** Letting `--max-warnings` grow is surrender. It only goes down.
- **Fixing five bugs in one diff.** Unreviewable, unbisectable. One PR per bug; skip-with-doc the rest.
- **Hardcoding live counts.** A test asserting `=== 3547` goes red on the next ingest. Assert invariants.
- **Claiming "fixed" from a synthetic repro.** Re-verify against the original user-facing conditions.
- **Skipping the diff-review because it's a solo build (no swarm).** The integrated-diff review catches seam/contract bugs your own tests can't — you wrote both sides and both their tests. Solo builds need it more, not less, especially watcher/observability code.
- **Reading "Pass-2 found new bugs" as the loop failing.** Each fix round opens the next round's findings; that's the loop working. Budget build → BLOCK → fix → verify(new defects) → fix.
- **"The helper dry-ran fine" = the cron is hardened.** No. The helper alone doesn't exercise the agent's post/merge loop. A new helper in a brief/digest cron needs a single-post guard + merge-back-by-id, verified on the first real scheduled run.
- **A preflight/healthcheck that SPENDS the budget it protects (the preflight paradox).** A probe placed before a rate/budget-limited op, hitting the SAME key the real op uses (per-IP quota, per-token credit, one-shot lock), consumes the budget and CAUSES the failure it checks for — e.g. a Reddit-RSS "preflight fetch" on a ≈1-fetch/window egress makes the real gather the 429. Don't add a separate probe against the same key: make the **first real operation itself the health signal** (keep on 200, mark down on failure, lean on the op's own retry/degrade). A separate probe is safe only against a DIFFERENT key/endpoint, or if its result IS reused as the first unit of real work. Also covers the dep-free curl-SOCKS transport (honoring a no-new-dep invariant when the native client can't proxy). See `references/post-build-diff-review-solo-builds.md`.

## Further reading (load when relevant)

- **`references/adversarial-cli-library-dogfood.md`** — the deliberate "try to break it" pass for a
  shipped CLI/library (not a web app — that's `qa`'s `web-functional` tier). The bug classes a "12 PASS, ship it"
  run hides: URL-scheme SSRF/local-file-read, garbage-input tracebacks vs graceful errors,
  verifier-checks-the-wrong-field, FAIL-vs-SKIP prerequisite-parity, a negative-control a weak target
  can't satisfy (build a deterministic target-independent proof instead), self-auditing the spec's
  ACs after declaring done, keyword-only args to block trust-boundary inversion, the **real-process
  concurrency double-send race + lock-neuter negative control**, the **per-resource `fcntl.flock` guard
  pattern** (non-blocking skip / crash-safe / critical-exempt / multi-host redeploy), **HTML-generator
  stored-XSS** (escape every field, fixed-lookup attribute values), and the **git-automation NUL-delimited
  (`-z`) filename rule** (§11: `git status --porcelain` / `git diff --cached --name-only` C-quote non-ASCII
  paths → a name-based secret scanner reads an empty blob and LEAKS a secret in a non-ASCII-named file, plus
  a silent coverage drop; read every porcelain/staged stream `-z` and iterate an array). **Load when
  hardening any shipped CLI/library tool, a concurrent queue/flush/worker, an HTML dashboard generator that
  renders user-controlled strings, or any git automation that loops over filenames (autocommit guard,
  pre-commit hook, lint-staged, changed-files CI step, mass-rename).**
- **`qa`** (the fleet QA master skill, `general` group) — the canonical "verify it actually works"
  skill: a router over web-functional / cli-library / api / accessibility / visual / perf / security /
  regression / release-gate / test-design tiers, all under one anti-fake-green evidence-and-verdict spine.
  **Run `qa` as the verification arm of any hardening pass** — when the artifact is a web app, its
  `web-functional` tier IS the browser-driven e2e failure-path hunt this skill calls for (it absorbed the
  old `dogfood` skill); for a shipped CLI/library, `qa`'s `cli-library` tier points back at
  `references/adversarial-cli-library-dogfood.md` below. **Load `qa` whenever you're hardening something
  with a user-facing or integration surface.**
- **`references/vendored-binary-wrapper-live-walk.md`** — hardening a wrapper around a\n  VENDORED BINARY/CLI you don't control: why a fully-green mocked-`subprocess` suite is\n  structurally blind to the binary's real output shape (the mocks and the product share\n  your assumption), the live-walk-every-subcommand rule, the bug class it catches\n  (output-field divergence like `logged_in` vs `authenticated`, systemic missing-`--json`,\n  a capability the wrapper assumed but the binary lacks → scope decision not a patch), plus\n  two adjacent traps: silent test-SKIP from a missing `pytest-asyncio` (verify `0 skipped` +\n  `asyncio_mode=auto`), and the anti-bot ATTACH-real-browser-don't-LAUNCH-headless backend\n  rule (CDP `connect_over_cdp`, detach-only close, fail-closed when unreachable). **Load when\n  hardening any code that shells out to a third-party CLI/binary, or a browser login/checkout\n  driver behind an anti-bot wall.**\n- **`references/config-knob-retune-exposes-latent-ordering-bugs.md`** — when the user retunes a\n  config knob (slot count, batch size, worker count, top-K, page limit), treat it as a hardening\n  trigger: the OLD value masks whole bug classes that the new value (usually a smaller one) makes\n  load-bearing. Covers the primary-vs-secondary sort-key collapse (a multi-dimensional ranking sorted\n  by ONE dimension looks fine at N=3, picks the same wrong bucket every time at N=1), the\n  reserve-K-slots-then-fill footgun at `K>=N`, the special-category-IS-the-answer-on-some-inputs trap,\n  and the rule to TEST KNOB EXTREMES (1 and max), not just the default. **Load when a build exposes a\n  tunable selection/batching/concurrency parameter, or when the user asks to change one.**\n- **`references/post-build-diff-review-solo-builds.md`** — running the senior Opus diff-review as
  a hardening gate on a SOLO build (not just a swarm): why solo builds need it more, the
  silent-failure-seam bug class in observability/watcher code (recovery lying about state, false
  STUCK alerts, error-swallow, storm-cap blind during a real incident), multi-passing the build,
  and the "a red hardening test is usually a TEST bug first" discipline. Also carries the
  **TIME-WINDOWED staleness-watchdog 5-bug checklist** (schedule-vs-detector slot mismatch, DST
  construct-time-offset, tz-DB-missing crash/silent-UTC, liveness-keyed-off-woke-up-not-succeeded,
  the alarm's own `_alert` swallowing delivery failure) and the **instrument-FIRST-overturns-the-
  spec's-own-"REAL BUG"-hypothesis-at-build-time** rule. Also carries the **recovery/all-clear
  alert-inversion** rule (a posture-delta that infers "recovered" from a finding DISAPPEARING
  announces a FALSE ✅ when the entity was removed administratively — retired/disabled/deleted —
  while still broken; gate the ✅ on healthy-NOW not absent-NOW, removal ≠ recovery, route a quiet
  🚫-retired note instead) + the reconcile/removal-sweep guards (effective-set guard, fraction cap,
  debounce, refuse-to-silence-a-failing-entity). **Load after building a
  non-trivial system before closeout, especially any watcher/healthcheck/detector/alerting code.**
- **`references/liveness-signal-must-reflect-current-state.md`** — the flock-mtime false-wedge class:
  a watcher reads a once-set/derived proxy (a lock FILE's mtime, a start-only timestamp, a PID-file
  ctime) as if it were live state, so it pages on "held/stuck for N hours" that's really just
  wall-clock since the file was created. The fix is a DIRECT current-state probe (`flock -n` /
  `fuser` / "is the connection answering") + an N-consecutive debounce (a single positive is normal
  in-flight work) + fail-safe-on-ambiguity (FREE/unknown resets the streak), with the LIVE held-lock
  e2e as the only real proof. Sibling to the staleness-watchdog "liveness keyed off woke-up not
  succeeded" bug. **Load when building/fixing any "has X been held/stuck/open/running too long?"
  watchdog, or when a duration-based alert flaps on a healthy system.**
- **`references/llm-cron-orchestration-hardening.md`** — hardening an LLM-prompt-driven cron\n  (brief/digest/triage) when you wire a new helper/script into it: why the helper dry-run isn't\n  the e2e, the single-post idempotency guard, the merge-back-by-id step + sanity check, and the\n  real 2026-06-09 morning-digest failure (4 posts in one run + pf-output unmerged → empty husk).\n  **Load when wiring a helper into an agent-driven cron prompt.**\n- **`references/shell-script-testability-seams.md`** — making a launchd/cron SHELL script (healthcheck/watchdog/autoheal, the `ai.agent.*-healthcheck` family) testable: extract logic into functions, inject every external dep (`codex`/`ps`/`kill`/auth-json/`notify`) via env overrides, add a `SOURCE_ONLY` guard, write RED-provable failure-path tests with stub binaries, prove the guards have teeth. Includes the BSD-`ps`-has-no-`etimes`, instrument-before-guard, and `$(…)`-redaction-mask pitfalls. **Load when hardening a fleet shell healthcheck/watchdog.**\n- **`references/threading-optional-kwarg-through-injected-seams.md`** — hardening a NEW optional
  parameter (`cookies=`, `proxy=`, `timeout=`) threaded down a call chain that has a
  dependency-injection / monkeypatch seam. Covers the signature-aware forwarder (`_maybe_cookies`)
  that keeps 2-arg injected runners working, the swallowed-`TypeError`-from-a-narrow-stub mis-route
  (widen every monkeypatched stub to `lambda t, **k:` in the same diff), conditional kwarg at the
  fan-out caller, param-beats-env precedence with a 3-test matrix, the env-scrubbing live regression
  lock that proves the value reaches the real subprocess, and the CLI hard-cap-vs-prompt-gate
  (`--limit` vs `--max-videos`) ordering rule. **Load when adding an optional arg that must flow
  through an injectable/stubbed call chain.**
- **`references/callsite-contract-and-subprocess-seam-tests.md`** — two reusable patterns from
  hardening a fleet of scheduled scripts that share one delivery tool: (1) the **fleet-wide
  call-site contract test** that parses a tool's real CLI flags + function kwargs FROM ITS SOURCE,
  scans every caller incl. `$VAR` indirection, RED-proves against the original bug, and uses a
  `KNOWN_BROKEN_DORMANT` skip-list guarded by a "still unscheduled?" check; (2) the
  **env-injectable subprocess seam** (override the binary + timeout, prod defaults unchanged) so an
  e2e drives the REAL `subprocess.run` with a latency/exit-controllable stub — plus the multi-chunk
  delivery-timeout sizing rule and the "monitor that fails silently" / sibling-commit-sweep /
  allowlist-gitignore pitfalls. **Load when hardening many callers of one shared tool/CLI, or a bug
  that lives in a `subprocess.run(..., timeout=N)` call.**
- **`references/route-and-cache-test-patterns.md`** — two concrete, reusable hardening patterns:
  (1) the route-level handler test that mocks boundaries to prove the *wiring* (the expensive/CLI
  fallback is never called on hardened paths) incl. the in-process-cache-leaks-across-tests and
  `vi.fn()`-spread-args-trips-tsc gotchas; (2) the read-through cache invariant table (cold MISS /
  warm HIT 0 reads / TTL boundary / **key-set-change invalidation** / TZ day key / errors-never-poison
  / escape hatches) plus the pure-module + BigInt-id + sorted-key-hash design rules and the
  three-run live smoke proof. **Load when hardening an HTTP route or a read-through cache.**
- **`references/render-pipeline-and-vacuous-gate-hardening.md`** — hardening a RENDER/transform\n  pipeline whose deliverable is a generated document (HTML report, page, export): the\n  \"feature shipped but no LIVE render exercised it\" gap (seam-unit-green + toy-fixture screenshot ≠\n  the shipped artifact has the feature; add an offline re-render harness that replays the real\n  persisted data network-free), and the **vacuous integrity gate** (a \"every link resolves\" publish\n  gate passes on a zero-anchor doc → presence-floor flag + scope guard + strip-the-markers RED proof).\n  The production-artifact twin of `certification-fixture-teeth.md` §2. **Load when hardening any code\n  that renders a user-facing document behind an integrity/consistency publish gate.**\n- **`references/certification-fixture-teeth.md`** — when the artifact you're hardening **is itself
  a regression net / certification harness / gold-set gate**, the adversarial pass turns inward:
  does the gate actually RED when its invariant breaks? Three teeth-failures a "4/4 PASS" run hides —
  (1) an assertion you can't make red is unproven, and **engine-global mutation can't isolate a bar**
  (inject a forced-score synthetic probe after the real items score through the unperturbed engine;
  the only permitted co-red is a documented entailment whose direction you DERIVE from live state, not
  hardcode); (2) **vacuous pass** — a universally-quantified "no X violates Y" gate passes trivially on
  an empty/hollow fixture, so add a non-emptiness population floor (`MIN_CORPUS`, ≥1 per class, locked
  `< len(manifest)`); (3) **non-discriminating** — an assertion that passes on arithmetic coincidence
  (off-topic-safety checking only `final < gate` when nothing structurally gates the term) instead of
  the mechanism's own output; assert the breakdown term/parsed field, revert-the-guard-does-it-red, and
  the breakdown term/parsed field, and pair each "must be 0" with a "must NOT be 0" scope-guard. Plus fold the harness's own suite into
  `verify` (a cert harness nobody runs is the most vacuous pass of all). **§2b extends the vacuous-pass
  rule to an INTEGRITY/PUBLISH gate over GENERATED OUTPUT: a link/structure validator passes on output
  where the checked FEATURE is entirely ABSENT (no anchors → nothing dangles → "ok"), shipping the
  artifact missing its headline feature — the youtube-notebooklm "v4 incident" where an un-anchored
  report passed `check_anchor_integrity`. Fix = a PRESENCE FLOOR tied to a structural precondition
  ("if the output has Sources rows it MUST have clickable anchors, else FAIL") + an e2e through the
  real producer; the seam-level unit suite was green and blind to it.** **Load when hardening a
  regression fixture, gold-set/eval harness, self-test, mutation matrix, a publish/integrity gate that
  validates a rendered artifact, or any gate whose job is to fail loudly.**
- **`references/hermetic-test-isolation-side-effecting-functions.md`** — when a test calls a real
  production function that writes operator state (`~/` cache/hash/cursor file) or spawns a real
  notifier (Telegram/Discord/`notify.py`/email/webhook) with no isolation, every suite run silently
  mutates real state and can fire a real live alert — a self-inflicted bug that looks like "the
  environment/provider changed." Covers the call-time-env-resolved paths + kill-switch + require-after-env
  fix, the two RED-provable regression guards, the `grep -rn "<magic alert value>"` root-cause shortcut,
  and the snapshot-diff proof (full `verify` leaves the real state file byte-identical).
  **Load when a test touches a function that writes outside the sandbox or fires an alert.**
- `test-driven-development` — the per-unit RED-GREEN loop, the 6-phase dispatcher stress pattern, structural-invariant tests for transform pipelines, skip-with-documentation, live-provider canaries. **Load alongside this skill.**
- `coding-guardrails` — the shared discipline reference for smallest viable diffs and the prove-with-evidence success test: real evidence on the real path, never asserted success.
- `prd-closeout` — the evidence gate this hardening pass feeds. Closeout BLOCKs if hardening was skipped.
- `prd-review-pipeline` — senior adversarial review of the spec/design; complements code-level hardening.
- `systematic-debugging` — when a hardening test surfaces a real bug, root-cause it before patching.
- `requesting-code-review` — pre-commit security scan + quality gates on the hardening diff.

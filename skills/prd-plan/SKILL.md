---
name: prd-plan
description: "Break an approved PRD/spec phase into bite-sized TDD implementation tasks: exact file paths, copy-pasteable code, exact test commands, RED-GREEN-REFACTOR ordering, commit-per-task, smoke-test-as-a-step. The serial single-executor (you or one subagent via subagent-driven-development) counterpart to prd-swarm-plan. Use after prd-spec + prd-review-pipeline, on approved phases, before building. (Formerly 'writing-plans'.)"
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, design, implementation, workflow, documentation]
    related_skills: [prd-spec, prd-swarm-plan, subagent-driven-development, test-driven-development, requesting-code-review]
---

# PRD Plan (Implementation Task Breakdown)

> **Where this sits in the prd-* family:** this is the **serial, single-executor** half of the
> implementation-planning stage — it turns one approved `prd-spec` phase into a bite-sized TDD task
> list that you (or one subagent via `subagent-driven-development`) work through in order. Its
> **parallel twin is `prd-swarm-plan`**, which compiles the same approved phase into a multi-worker
> Kanban DAG when the work fans out across disjoint write scopes. Pick this one for serial work;
> reach for `prd-swarm-plan` when the topology is genuinely parallel. Full lifecycle:
> `skill_view(name='prd-spec', file_path='references/lifecycle.md')`.
>
> For **who owns which concept** in this suite, see the ownership map:
> `skill_view(name='prd-spec', file_path='references/prd-suite-map.md')`.

## Overview

Write comprehensive implementation plans assuming the implementer has zero context for the codebase and questionable taste. Document everything they need: which files to touch, complete code, testing commands, docs to check, how to verify. Give them bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume the implementer is a skilled developer but knows almost nothing about the toolset or problem domain. Assume they don't know good test design very well.

**Core principle:** A good plan makes implementation obvious. If someone has to guess, the plan is incomplete.

## When to Use

**Always use before:**
- Implementing multi-step features
- Breaking down complex requirements
- Delegating to subagents via subagent-driven-development

**Don't skip when:**
- Feature seems simple (assumptions cause bugs)
- You plan to implement it yourself (future you needs guidance)
- Working alone (documentation matters)

**Seam with `prd-spec`:** if you do not have an authored PRD/spec yet, start with `prd-spec`; `prd-plan` expands an approved PRD phase into bite-sized TDD implementation steps. `prd-spec` owns the spec document and per-phase verification intent; this skill owns the executable task breakdown.

## Bite-Sized Task Granularity

**Each task = 2-5 minutes of focused work.**

Every step is one action:
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

**Too big:**
```markdown
### Task 1: Build authentication system
[50 lines of code across 5 files]
```

**Right size:**
```markdown
### Task 1: Create User model with email field
[10 lines, 1 file]

### Task 2: Add password hash field to User
[8 lines, 1 file]

### Task 3: Create password hashing utility
[15 lines, 1 file]
```

## Plan Document Structure

### Header (Required)

Every plan MUST start with:

```markdown
# [Feature Name] Implementation Plan

> **For Hermes:** Implement this plan task-by-task — inline for serial work, or via the subagent-driven-development skill to dispatch a fresh subagent per task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

### Task Structure

Each task follows this format:

````markdown
### Task N: [Descriptive Name]

**Objective:** What this task accomplishes (one sentence)

**Files:**
- Create: `exact/path/to/new_file.py`
- Modify: `exact/path/to/existing.py:45-67` (line numbers if known)
- Test: `tests/path/to/test_file.py`

**Step 1: Write failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify failure**

Run: `pytest tests/path/test.py::test_specific_behavior -v`
Expected: FAIL — "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify pass**

Run: `pytest tests/path/test.py::test_specific_behavior -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Writing Process

### Step 1: Understand Requirements

Read and understand:
- Feature requirements
- Design documents or user description
- Acceptance criteria
- Constraints

### Step 2: Explore the Codebase

Use Hermes tools to understand the project:

```python
# Understand project structure
search_files("*.py", target="files", path="src/")

# Look at similar features
search_files("similar_pattern", path="src/", file_glob="*.py")

# Check existing tests
search_files("*.py", target="files", path="tests/")

# Read key files
read_file("src/app.py")
```

### Step 3: Design Approach

Decide:
- Architecture pattern
- File organization
- Dependencies needed
- Testing strategy

### Step 4: Write Tasks

Create tasks in order:
1. Setup/infrastructure
2. Core functionality (TDD for each)
3. Edge cases
4. Integration
5. Cleanup/documentation

### Step 5: Add Complete Details

For each task, include:
- **Exact file paths** (not "the config file" but `src/config/settings.py`)
- **Complete code examples** (not "add validation" but the actual code)
- **Exact commands** with expected output
- **Verification steps** that prove the task works

### Step 6: Review the Plan

Check:
- [ ] Tasks are sequential and logical
- [ ] Each task is bite-sized (2-5 min)
- [ ] File paths are exact
- [ ] Code examples are complete (copy-pasteable)
- [ ] Commands are exact with expected output
- [ ] No missing context
- [ ] DRY, YAGNI, TDD principles applied

### Step 7: Save the Plan

```bash
mkdir -p docs/plans
# Save plan to docs/plans/YYYY-MM-DD-feature-name.md
git add docs/plans/
git commit -m "docs: add implementation plan for [feature]"
```

## Principles

### DRY (Don't Repeat Yourself)

**Bad:** Copy-paste validation in 3 places
**Good:** Extract validation function, use everywhere

### YAGNI (You Aren't Gonna Need It)

**Bad:** Add "flexibility" for future requirements
**Good:** Implement only what's needed now

```python
# Bad — YAGNI violation
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
        self.preferences = {}  # Not needed yet!
        self.metadata = {}     # Not needed yet!

# Good — YAGNI
class User:
    def __init__(self, name, email):
        self.name = name
        self.email = email
```

### TDD (Test-Driven Development)

Every task that produces code should include the full TDD cycle:
1. Write failing test
2. Run to verify failure
3. Write minimal code
4. Run to verify pass

See `test-driven-development` skill for details.

### Frequent Commits

Commit after every task:
```bash
git add [files]
git commit -m "type: description"
```

## Common Mistakes

### Vague Tasks

**Bad:** "Add authentication"
**Good:** "Create User model with email and password_hash fields"

### Incomplete Code

**Bad:** "Step 1: Add validation function"
**Good:** "Step 1: Add validation function" followed by the complete function code

### Missing Verification

**Bad:** "Step 3: Test it works"
**Good:** "Step 3: Run `pytest tests/test_auth.py -v`, expected: 3 passed"

### Missing File Paths

**Bad:** "Create the model file"
**Good:** "Create: `src/models/user.py`"

### Proof harnesses first for high-invariant phases

When an approved PRD phase's risks are about proving invariants — one path not reachable, no live actuation, behavior-preserving rename, read-only audit, no unredacted egress — make the first implementation tasks build the **proof harnesses** before the behavior change. Examples: golden sweep with dispatch-branch capture before a rename; permanent old-name guard before deprecating a module; filesystem-write guard before running a read-only audit; provider-spy/null-dependency tests before retiring an internal LLM path; mock/non-live client guard before tests that look like house actuation. This gives every later task a real gate and prevents a large phase from ending with theater checks bolted on afterward.

### A measurement/probe Phase-0 task FALSIFIES spec assumptions — that's the job; fix forward, don't bend the test to the assumption

When the approved spec opens with a Phase-0 "ground-truth probe / coverage / baseline" task (the kind whose whole purpose is to measure reality before you build against it), expect it to **disprove something the spec assumed** — that is the phase succeeding, not failing. Three things to do when it does, all proven 2026-06-16 (the voice assistant routing Phase-0 probe):

- **A test that bakes YOUR assumption is the bug, not the code.** A probe test asserted "turn on the kitchen lights" is a curated capability; the real router returned `unknown` (per-room light *commands* aren't curated; only status queries are). The honest fix is to **re-anchor the test to the ground-truthed value** (assert on a known-handled utterance you actually verified, e.g. "what lights are on" → `query_status` conf 0.95) and keep the **load-bearing invariant** (the chat utterance must NOT overmatch) — NOT to delete the invariant or fudge the assertion green. Ground-truth the real return shape with a 5-line probe *before* writing the assertion.
- **The assumed live transport may not be the live path.** The spec assumed an HTTP `POST /v1/command` "live pass"; the HTTP API wasn't even running — the live system called the library **in-process**. So the real live pass is the probe run in-process on the deployed host (which doubles as a config-drift check: offline-vs-live was byte-identical → zero drift). Correct the plan to the proven path and record it; don't force the assumed transport.
- **A design knob the spec wants to "tune empirically" can turn out non-existent.** The spec's confidence-floor decision assumed a confidence gradient to threshold on; the probe showed the router emits **bimodal** confidence (0.95 or 0.0), so the overmatch fires at the SAME score as correct matches — a floor cannot separate them yet, and the fix must happen at the *matcher* level instead. Record this in the baseline doc as a finding that **changes the downstream design**, and flag it to the user before proceeding, rather than carrying a floor that "looks tunable" but is inert.

The reusable shape: a probe phase produces a `docs/PHASE-0-<area>-baseline.md` capturing coverage gap, real overmatches, the actual confidence/latency distribution, and **which spec assumptions it falsified** — that artifact, not a green test, is what unblocks the next phase. (Same family as prd-spec's "Phase-0 live probe falsifies the assumed flow"; this is the *plan-execution* corollary.)

### Phase-N corollary: a probe finding from Phase 0 IS the fix-forward design of the next phase

The Phase-0 baseline's "findings that change downstream design" are not footnotes — they become **named, in-scope tasks** in the next phase's plan, each with its own RED test, fix, and PRE→POST diff. Proven 2026-06-16 (the voice assistant routing Phase 1, sequel to the Phase-0 probe above):

- **The Phase-0 overmatch became the Phase-1 matcher fix.** The probe recorded `"should I turn on the lights"` → `device_control` 0.95 (a question actuating). Phase 1 fixed it *at the matcher* (deliberative-question stems `should I / shall we / do I / what if I` suppress an ACTION capability match but never a `query_status` — so `"what lights are on"` still resolves). The fix is principled and general (a stem list), not a one-utterance special-case.
- **The Phase-0 coverage gap became a Phase-1 in-scope task with the real root cause.** "Per-room light commands return `unknown`" turned out to be a **determiner gap**: the curated alias was `"turn on kitchen lights"` and the filler word in `"turn on **the** kitchen lights"` broke contiguous-phrase matching. Fix = determiner-tolerant matching (`_FILLER_DETERMINERS = {the,a,an,my,our}` stripped from both sides for the containment comparison only, never from the stored utterance). Always find the *mechanism* behind a coverage gap before writing the fix — it's usually one general rule, not N missing aliases.
- **The Phase-0 "knob is inert" finding gets RE-MEASURED, not assumed-fixed.** Phase 0 said the confidence floor was inert (bimodal 0.95/0.0). Phase 1's POST diff re-measured: the new adjunct introduced a *third* confidence band (built-ins at 0.90), so the gradient now exists and the floor is no longer inert. Record the re-measurement explicitly in the PHASE-N result doc; don't carry the Phase-0 verdict forward as still-true.

### An intentional behavior change will turn a pre-existing test RED — UPDATE the test, don't revert the feature

When a phase's whole point is to change behavior (e.g. "absorb HA-native built-ins into HACR" = built-ins that *used* to delegate to HA Assist now resolve locally), an existing test that encodes the OLD behavior will fail. This is the **intended** change, not a regression. The discipline (proven 2026-06-16):

1. **Read the failing test and confirm it asserts the old contract** the spec decision deliberately changed. (Here: a delegate test asserted `"what time is it"` falls through to HA Assist — exactly what RD-1 removed.)
2. **Update it to the new contract AND add a regression guard for the new behavior** — don't just relax the assertion. Re-point the fall-through test at a *genuinely* unknown utterance (`"tell me a joke"`), and add a new test asserting the built-in is now handled locally and never reaches the old delegate.
3. **Comment the test with the decision ID + date** (`# RD-1, 2026-06-16: built-ins absorbed into HACR`) so the next reader knows the change was intentional, not an accidental loosening.
4. **The trap to avoid:** "make the suite green" by reverting the feature behavior or deleting the assertion. The failing test is *evidence the feature works* — treat it as a contract migration, not a bug.

### Mutation-test a "this gate is load-bearing" claim by clearing bytecode, not just the source

A `prd-spec`/`prd-plan` proof that a threshold/floor/flag is **active, not decorative** (e.g. the RD-8
"flip `RD8_FLOOR` 0.5→0.0 and the below-floor test MUST now fail" check) has a sharp footgun: if you mutate
a constant in place (`sed -i`), run the test, then restore the source, the **stale `.pyc` can outlive the
restore** and the interpreter loads the mutated bytecode — so a *restored* file reads correct on disk
(`grep` shows 0.5, `git status` clean) yet the test stays red, looking like a real regression you can't
explain. Proven 2026-06-16 (the voice assistant routing Phase 3, RD-8 mutation check).

Do the mutation check cleanly:
1. **Back up the file, mutate, run, restore from the backup** — and then **delete the `__pycache__`**
   (`find . -name __pycache__ -path '*<pkg>*' -exec rm -rf {} +`) before re-running the suite. The `.pyc`
   mtime can beat the restored `.py` when the round-trip is fast, defeating Python's staleness check.
2. **Tell disk-truth from runtime-truth the instant a "restored but still red" mystery appears:** print
   what the interpreter actually loaded — `python -c "import pkg.mod as m; print(m.__file__, m.CONST)"`.
   If `grep` says 0.5 but the import says 0.0, it's a bytecode-cache lie, **not** a source bug — clear the
   `.pyc` and move on; do NOT start "fixing" correct source.
3. Cheaper alternative that sidesteps the cache entirely: prove the gate is load-bearing **without editing
   the module** — `monkeypatch.setattr(mod, "CONST", 0.0)` inside a throwaway test, or assert
   `decide(...)` directly across the boundary. Reserve `sed`-and-restore for when monkeypatch can't reach
   the constant.

(Same instrument-before-theorizing reflex as the Obsidian "edit vanished = the open app, not a phantom
path" lesson: when on-disk truth and observed behavior disagree, print what's actually loaded before
blaming the source.)

### Deploy to the checkout, but DON'T flip the live hot path until the gated cutover

When the running production service imports the code in-process (e.g. the brain imports HACR from a git checkout under its own venv), you can **prove a phase live without activating it**: push, pull the checkout to HEAD, install pinned deps into the *service's actual interpreter*, and run the probe under that exact `python` against the deployed checkout. That gives a real live + zero-config-drift proof (offline-vs-live byte-identical) **without restarting the service** — so production behavior is unchanged. Per the user's standing rule, the live-routing flip / service restart is the gated, user-present cutover phase, never folded into a build phase. Find the service's real interpreter + import path first (`systemctl --user cat <svc>` → `ExecStart` venv; grep the entrypoint for the `sys.path.insert`/`*_PATH` env it imports from) so the probe runs the same bytes production runs.

### Before reconciling a live NON-GIT mirror to its git checkout, DIFF them — the mirror may hold an uncommitted prod hotfix

When a service runs from a **non-git mirror dir** and the cutover plan is "repoint its `WorkingDirectory`
to the git checkout," do NOT treat that as a no-op config flip. A long-lived mirror accumulates
**uncommitted live hotfixes** — edits made directly on the box, in production, that were never committed.
Blindly repointing to git silently **reverts** them. Proven 2026-06-16 (the voice assistant Phase-4 prep): the live
brain ran from a mirror whose `memory.py` had been hotfixed to point mem0 at the self-hosted OSS instance
(`127.0.0.1:8888`, bare `/memories`, `X-API-Key`); the git checkout still had the dead cloud endpoint
(`api.mem0.ai`, `/v1/memories/`, `Token`). The live `.env` set **only** `MEM0_API_KEY` — so the brain
hit OSS purely via the mirror's **code defaults**. A blind reconcile would have broken mem0 with zero
error, just wrong answers.

The safe reconcile sequence:
1. **`diff -rq <mirror> <git-checkout>`, code-only** (filter `__pycache__|*.pyc|*.bak|.env|*.last-acceptance`).
   An empty diff means safe; ANY differing file is a fork to resolve before touching the service.
2. **For each differing file, compare mtimes to decide which side is truth.** The split is usually clean:
   files for the process *already on git* → git is newer (committed updates, mirror is stale leftovers);
   files for the process *still on the mirror* → **mirror is newer = the uncommitted live hotfix**. Don't
   assume; `stat -c %Y` both sides.
3. **Land the mirror-newer hotfix into git FIRST** (its own commit, RED-proven if it's a behavioral
   default), so the checkout the service will move to is functionally identical to what it runs today.
   Verify byte-identical *behavioral* lines (not comments) between your committed version and the mirror.
4. **Make env-overridable defaults match LIVE REALITY, not the old upstream default.** Here OSS became the
   *default* (with the cloud Token path kept as an env escape hatch) precisely because the live `.env` did
   NOT override it — if the default doesn't match what production actually does, the reconcile regresses on
   restart. Confirm what the live `.env` actually sets before choosing the default.
5. Only then repoint `WorkingDirectory` + `daemon-reload`. The change is inert until the next restart
   (the gated cutover step) — confirm via `/proc/<pid>/cwd` that the running process is still on the old
   path, proving zero live impact from the config edit alone.

The reusable reflex: **"reconcile mirror→git" is a content-merge, not a path swap.** The mirror is a
second, undocumented source of truth until you've proven the diff is empty or merged. The matching
read-only pre-cutover gate (`/proc/<pid>/cwd` proves the live PROCESS runs the checkout, not SHA-on-disk)
is the I-R9 pattern — build it as a `scripts/live-git-drift-check.sh` and run it against the host before
each restart.

## Spec → v0.1 Implementation Cut Pattern

For large multi-axis specs, the user prefers a **two-document structure** — a frozen north-star PRD plus a strict v0.1 implementation cut with a trigger-keyed roadmap table. That pattern is an **authoring/spec-structure decision** and now lives in the `prd-spec` skill ("Spec → v0.1 Implementation Cut Pattern"). Author the two docs there; bring the approved v0.1 cut here for the bite-sized TDD task breakdown.

### A Phase-0 probe tests the COMMON shape — the DEGENERATE shapes (1, 0, empty) get caught later, so test them explicitly

A Phase-0 ground-truth probe naturally exercises the *representative* input (the 2-of-3 case, the
multi-item list, the populated dir) and certifies the architecture off it. But the bug that ships is
often in the **degenerate boundary**: exactly one item, zero items, an empty set — shapes the probe
didn't think to feed. Proven 2026-06-27 (QMD code-collection): Phase 0 proved a brace-include
`{repoA,repoB}/**` works (2 repos) and the build certified it; the single-element form `{repoA}/**`
silently indexes **zero** files (minimatch braces need ≥2 alternatives — it must be a bare
`repoA/**`). That meant if the include-list ever shrank to one repo, the whole collection would
silently index nothing — caught only by the Phase-5 removal-reconciliation test (shrink to 1), never
the Phase-0 probe (which tested 2+). Discipline: when a probe validates a mechanism over a
representative N, add explicit build-phase tasks for **N=1 and N=0** (and any other degenerate count)
with their own RED tests — a green probe on the common shape is NOT coverage of the boundary shapes.
Fix the generator to special-case the singleton (`return items[0] if len(items)==1 else "{"+",".join+"}"`).

### The SUPERVISED first-live-mutation phase is its own gate — green unit tests do NOT cover the tool-boundary

When a phase first writes to a LIVE shared store (embed an index, populate a DB, push a config the
service reads), run it SUPERVISED as a distinct gated step, even with a fully-green test suite — the
bug that bites lives at the **tool boundary your tests mocked past**, not in your logic. Proven
2026-06-27 (QMD code-collection first embed): every unit+integration test was green, but the indexer
**globs by its own pattern and never ran our content secret-lint** — so 17 secret-bearing files the
lint had flagged got indexed anyway. The tests proved "our lint excludes them"; they didn't prove
"the indexing tool honors our exclusions." Caught it because the supervised embed verified the LIVE
index (`qmd ls`), not just the test fixtures. Discipline:

- **Name the seam between YOUR gate and the THIRD-PARTY actor.** If a tool ingests by its own
  rule (glob, scan, query), your filter/lint must be translated into THAT tool's exclusion mechanism
  (here: lint exclusions → exact-path `ignore:` entries), or the tool ignores your gate entirely.
  A test that exercises your gate in isolation can't see this — add an E2E that inspects the tool's
  actual output after a real run.
- **Make the first live run reversible + observed:** quiesce → apply → verify the live artifact →
  prove the SECURITY property on the live store (e.g. "grep the indexed content for secrets = 0"),
  not just on your pre-filter list. Then the real smoke query.
- **A long batch op can orphan a child past its parent.** The bounded-embed wrapper exited while a
  final `qmd embed` child kept running; "done" = the work signal vanished (pending=0, the tool omits
  the line at 0), NOT the parent PID exiting. Poll the work-state, not the launcher.

### A noisy gate/detector firing on real data: GROUND-TRUTH the hits before trusting OR muting the count

When a security/lint/validation gate fires a big count on first contact with real data, do NOT
either trust it wholesale (alert-fatigue, cry-wolf) or mute it (you'll bury the one real hit). Triage
the hit DISTRIBUTION against ground truth, then tune precision while keeping the high-confidence lane
loud. Proven 2026-06-27 (QMD secret gate over 4,589 real code files): 135 raw hits, triaged to
~all false (`op://` = safe 1Password references; `generic_secret` = type-hints/env-reads/dotted-refs/
`'***'` fixtures) — but 1 was a REAL leak (live API keys in a tracked config). Tuned 135→17 by
dropping the safe-reference detector and requiring the generic detector's VALUE to be high-entropy
(not an identifier/env-read/placeholder); kept the high-confidence key detectors (sk-…/AIza/bearer)
loud because that lane caught the real one. Rules: classify by detector KIND and by whether the
matched VALUE is a literal secret vs a code reference; a `keyword: identifier` / `keyword:
process.env.X` / `keyword: data.attr` match is code, not a leak; tune a SCOPED copy of the detector
set, never the shared one another consumer depends on; the gate staying clean is the proof, a small
real reviewable list is the steady state.

### A build-phase EVAL must run on the SAME model the production path uses — a weak grader gives a false verdict

When a phase gates on a model-mediated decision (a save/no-save rubric, a classify, a routing call), the
eval MUST exercise the model the **production code actually runs**, not a cheap stand-in. Proven 2026-06-27
(mem0-in-background-review save-eval): the review fork inherits `agent.model` = claude-opus-4-8, but the
first eval ran on gpt-5-nano "because it's cheap" → wildly unstable 67–92% recall across runs and false
misses of genuinely-settled facts → the eval FAILED and looked like the *rubric* was broken. On the real
fork model the same fixtures gave a clean 100% recall (Wilson LB 0.839) / 0% false-save. The rubric was
fine; the **grader was unrepresentative**. Discipline:
- **Find what model the production path uses** (`grep model=agent.model` / the service's configured model)
  and point the eval at THAT (or an equally-capable peer), via whatever transport reaches it. A relay you
  already have (e.g. `claude-bpp` at `localhost:18811`, OpenAI-style `/v1/chat/completions`, no auth — the
  rate-limit-headroom relay the user flagged) beats the senior single-instance transport for a 30–60-call eval
  that hits 429/503; add `429/5xx` backoff + gentle pacing.
- **A weak-grader FAIL is not a rubric-fix signal until you've re-run on the real model.** Don't harden the
  prompt to satisfy nano — you'll over-constrain it for the model that never had the problem. (Do fold
  genuine rubric gaps the *real* model also exhibits — here the real model over-saved speculation/one-off
  requests at 20% false-save until the clause excluded "I might / thinking about / remind me / transient
  events"; that fix held on the real model, so it was real.)
- General rule: **match the eval substrate to the production decision-maker** — same model, same prompt
  assembly (import the REAL prompt/clause constants, don't paraphrase them in the eval).

### A CALIBRATION eval can prove the spec's whole MECHANISM doesn't exist on real data — then the knob is the wrong design, not a tuning task

Distinct from "a tunable knob turns out inert" (the voice assistant bimodal-confidence): sometimes a 3-arm calibration
eval proves the *signal the spec is built on cannot do the job at any setting*. Proven 2026-06-27 (mem0
dedup D2): the spec's Tier-2 was "skip a write if embedding cosine ≥ threshold." A 65-pair, 3-arm fixture
(reworded-SAME / high-cosine-but-DISTINCT incl. contradictions / low-sim-distinct), embedded with the
store's real embedder, showed reworded-dup cosines (0.58–0.92) **OVERLAP** contradiction cosines
(0.61–0.99) — value-flips ("freshness 0.02"→"0.10" = 0.989) embed HIGHER than genuine paraphrases. So
there is **no threshold with non-zero dup-catch AND zero contradiction-swallow**. The honest output is not
a tuned number — it's "this mechanism is unsafe here; defer the job to the tier that can do it (an LLM
reconcile that FLAGS, never auto-suppresses)." Discipline:
- **A calibration fixture needs the ADVERSARIAL near-miss arm**, not just dup-vs-distinct: high-signal-but-
  semantically-opposite pairs (Schwab/Fidelity, "GPU 5090"/"3090", IP `.5`/`.208`). A 2-arm sweep hides the
  overlap that kills the design.
- **Report per-band contradiction-swallow, not just precision/recall.** The kill metric is "how many true
  contradictions land in the would-skip band" — if it's ever non-zero where catch is non-zero, the
  auto-skip is wrong (an auto-merge on cosine silently eats the user's *corrected* fact).
- **A calibration eval PASSES when it establishes the safe operating point** — including the finding that
  no safe auto-skip threshold exists (→ write-first, defer to LLM). Don't bend the gate to force a green
  threshold; the characterization IS the deliverable.

### A config knob you EXPOSE but never READ is theater — wire it or delete it, and prove it load-bearing

Distinct from the bytecode-cache mutation footgun above: that one is "the gate IS active but the test lied";
this one is "the gate was never active because nothing reads the knob." Proven 2026-06-28 (QMD-in-mem0,
self-caught mid-build). I exposed a `mem0_budget_s` config key, documented it in the spec as INV-4a/AC12
("the mem0 leg has its own budget"), defaulted it sensibly — and **no code path ever read it**. The
invariant was claimed in the spec and the AC list, but the field was decorative: a future reader would
trust a guarantee that did not exist. The discipline:

- **Every config knob the spec names as an invariant MUST have a code path that reads it AND a test that
  fails when it's violated.** If you can't write a test that goes red by toggling the knob, the knob is
  doing nothing — either wire it into real behavior or strike it from the spec. Don't ship a knob whose
  only effect is to make the spec *look* complete.
- **The honest fix is to make it load-bearing, not to quietly drop the AC.** Here: the mem0 leg's elapsed
  time is measured (`t_start = time.monotonic()` at the top of the prefetch `_run`), and if it overran
  `mem0_budget_s` the additive QMD leg is **skipped entirely** (a slow mem0 must not be made worse by
  stacking a second multi-second leg), with the QMD deadline further clamped to the time actually
  remaining before the join ceiling. Then AC12 (`mem0-over-budget → QMD skipped`, asserted with a spy
  that the QMD call count is 0) genuinely goes red if the budget check is removed.
- **Self-audit reflex at closeout:** before declaring a spec's invariants proven, grep each named
  config key / threshold / flag for a *read site* in the implementation (`grep -n KNOB_NAME impl.py`).
  Zero reads = decorative = unproven invariant. This catches "I added the knob to the config schema and
  the spec but forgot to consume it" — a failure mode that green unit tests on the *other* paths happily
  hide.

### Bounding a network leg in a hot path: a per-read socket timeout does NOT defend an SSE/keepalive trickle — only a wall-clock watchdog that shuts the socket does

When a plan adds a network call to a latency-bounded hot path (here: a QMD MCP query inside mem0's
every-turn prefetch, ceiling 10s), the naive "set `timeout=` on the connection" is a **false guarantee**.
Proven 2026-06-28 (QMD-in-mem0, was pass-1 review blocker B1, then confirmed by an adversarial test):

- **A socket/read timeout only fires on an IDLE socket.** An SSE `text/event-stream` endpoint that dribbles
  a keepalive comment (`: keepalive\n\n`) every 0.2s keeps the socket *active* forever — the per-read
  timeout never trips, and the call hangs past the budget indefinitely. The connection-level `timeout=N`
  defends connect + total-idle, NOT a slow-but-alive stream.
- **The defense is a single wall-clock deadline enforced by a watchdog that tears down the live socket.**
  `threading.Timer(deadline_s, _trip)`; `_trip()` does `sock.shutdown(socket.SHUT_RDWR)` + `conn.close()`,
  which makes the blocked `read()` raise immediately. Always `timer.cancel()` in a `finally`, and have the
  whole helper swallow any exception to `[]` so a QMD failure is degraded-safe (never raises into the turn).
- **`HTTPConnection.close()` alone is NOT enough** — `http.client` hands the raw socket to
  `HTTPResponse.read()`, so once the response object owns it, closing the *connection* doesn't interrupt the
  blocked read. Capture the actual socket handle (after `conn.request()` and again after `getresponse()`,
  reaching through `resp.fp.raw._sock`) and `shutdown()` *that* in the watchdog, not just the conn.
- **Prove it with an adversarial stub, not a happy-path test.** Stand up a tiny server that sends the SSE
  200 header then trickles keepalives and never completes; assert the helper returns `[]` within
  ~deadline+0.5s AND that thread/FD count is unchanged afterward (no leaked worker). A dead-endpoint test
  (connection refused) is necessary but does NOT cover this — connection-refused returns instantly; the
  trickle is the case that actually hangs production.
- **Measure cold vs warm and accept the cold-path degrade.** Cold daemon was 5.81s vs warm ~1.3s; with a
  4s deadline the *first* lookup after a daemon restart degrades to the primary-only result (safe), every
  warm call fits. Record this as a known, intentional degrade in the closeout rather than chasing it — and
  flag the number to the user so they can choose to bump the deadline.

## Smoke Test as a Plan Step, Not an Afterthought

Every implementation plan must have a smoke-test step before the "commit" step. **The bar is: actually invoke the thing end-to-end with a real input, not just unit tests.**

Why: unit tests pass while integration fails silently. The Codex `gpt-5.5` model gotcha (2026-05-13) was caught only because the smoke test ran a real fibonacci task through all three harnesses — unit-testing the dispatch script would have happily passed while codex returned HTTP 400 in production.

### Required shape of a smoke test step

1. **Same trivial task** through every variant (every harness, every model, every config branch). Fibonacci, hello-world, anything with a known correct answer.
2. **Verify output**, not just exit code. Read what came back and confirm it looks right.
3. **One row of evidence per variant.** "claude-code → ok 7.6s, codex → ok 3.6s, hermes-native → stub fires correctly."
4. **If a variant fails, debug, fix the config/code, re-run, capture the fix as a pitfall in the relevant skill.** Don't move to commit until all variants pass.

A plan that ends with "commit" without a smoke-test row is incomplete. A plan that hand-waves "verify it works" instead of specifying *how* is incomplete.

## Execution Handoff

After saving the plan, offer the execution approach:

**"Plan complete and saved. Ready to execute using subagent-driven-development — I'll dispatch a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed?"**

When executing, use the `subagent-driven-development` skill:
- Fresh `delegate_task` per task with full context
- Spec compliance review after each task
- Code quality review after spec passes
- Proceed only when both reviews approve

## Remember

```
Bite-sized tasks (2-5 min each)
Exact file paths
Complete code (copy-pasteable)
Exact commands with expected output
Verification steps
DRY, YAGNI, TDD
Frequent commits
```

**A good plan makes implementation obvious.**

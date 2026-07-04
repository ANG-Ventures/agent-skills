---
name: prd-spec
description: "Write PRDs, implementation specs, architecture proposals, or 'spec this out' documents that are testable from birth. Use this whenever the user asks for a PRD/spec/proposal, before PRD review, and before PRD-swarm planning. It produces a spec with per-phase verification blocks: unit/script checks, real e2e/integration checks for changed real paths, negative/adversarial cases for trust boundaries, and eval metrics for ML/heuristic/model work. Hand approved phases to prd-plan for bite-sized TDD task breakdown."
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, prd, specification, testing, evals]
    related_skills: [prd-review-pipeline, prd-swarm-plan, prd-plan, prd-closeout, coding-guardrails]
---

# PRD Spec (PRD / Spec Authoring)

Use this skill to write a PRD/spec that can survive review and implementation. The goal is not a nice narrative; the goal is a document that makes the build, tests, evals, and closeout obvious.

## Position in the lifecycle

This skill's place in the full lifecycle: see `skill_view(name='prd-spec', file_path='references/lifecycle.md')`. For **who owns which concept** in this suite, see the ownership map: `skill_view(name='prd-spec', file_path='references/prd-suite-map.md')`. **Immediately upstream:** `prd-interview`. **Immediately downstream:** `prd-review-pipeline`.

**Seam with `prd-plan`:** `prd-spec` owns the spec document and per-phase verification intent ("this phase must be proven by an e2e run of X"). `prd-plan` owns breaking an approved PRD phase into bite-sized TDD implementation steps. If you need step-level tasks after the PRD is approved, hand the phase to `prd-plan`.

## Required PRD shape

A good PRD includes these sections unless the project is genuinely tiny:

1. **Summary & Goal** — what changes and why now.
2. **Non-Goals** — what explicitly does not ship.
3. **Constitution / Invariants** — the non-negotiable security, data, and contract invariants the build must preserve.
4. **Resolved Decisions** — capture user decisions, tradeoffs, defaults, and why.
5. **Architecture / Design** — the system shape and data/control flow.
6. **Implementation Phases** — each phase has a Verification block (see below).
7. **Security, Privacy, Ops, Observability** — especially credentials, public surfaces, failure alerts, and rollback.
8. **Risks & Mitigations** — including false-premise and integration risks.
9. **Open Questions** — only the real ones; do not dump already-decided items. **When you present the spec to the user, ELABORATE each open question inline in the chat message as a full 1-3-1 (Problem → 2-3 Options with trade-off + counter-case → Recommendation → Definition of Done → Implementation Plan), not only as a doc bullet** — canonical rule in `prd-share` → "The delivery rule (canonical)" point 3; don't restate it.
10. **Acceptance Criteria** — objective, evidence-checkable, mapped to phases.

## Constitution / Invariants

Capture the rules the implementation is not allowed to violate, even while the shape of the solution changes. These become closeout checks for `prd-closeout`, not decorative prose.

Write invariants as concrete bullets with enough specificity to test later:

- **Security invariants:** credentials, auth boundaries, tenant/session isolation, destructive operations, public posting/sending, and secret redaction rules that must remain true.
- **Data invariants:** persistence, migration, retention, deletion, idempotency, ordering, dedupe, and data-loss boundaries that must remain true.
- **Contract invariants:** CLI/API/schema/event/webhook/backward-compatibility promises that existing callers or downstream agents depend on.

For each invariant, name the evidence that will prove it survived implementation:

```markdown
- **Invariant:** [non-negotiable rule]
  - *Why it matters:* [security/data/contract risk]
  - *Closeout proof:* [test, command, inspection, or manual evidence `prd-closeout` must check]
```

If an invariant forces a larger design, say so explicitly. If a planned feature is merely nice-to-have and not required by the goal or an invariant, keep it out of the build.

## Simplicity gate

Before handing the PRD to `prd-review-pipeline`, `prd-swarm-plan`, or `prd-plan`, run a scope checkpoint against `coding-guardrails` (the canonical minimal-diff/minimum-viable-change reference). Do not duplicate that skill here; reference it when the plan needs the detailed coding discipline.

Ask and answer in the PRD:

- Is this the **minimum** plan that solves the stated problem while preserving the Constitution / Invariants?
- Did any feature, abstraction, configuration surface, framework, or future-proofing enter without a concrete requirement, invariant, or acceptance criterion?
- Can v0.1 be smaller without breaking the goal, evidence path, or required contracts?

If the answer exposes speculative work, move that work to Non-Goals, a trigger-based roadmap entry, or a future phase that does not block the first useful implementation cut.

## Spec → v0.1 Implementation Cut Pattern (the user's preferred)

When a spec is large (4+ axes of complexity, multi-phase rollout, future-version vision), the user prefers a **two-document structure**:

1. **The full PRD / north-star** — captures the eventual architecture: all axes, all phases, all open questions, full registry/schema/data shape. Frozen as the long-term contract.
2. **A v0.1 implementation cut** — strict subset of the PRD. Just the smallest valuable slice that can ship. Everything else is scoped as a roadmap table with explicit **triggers** ("v0.2 ships when X happens," not "v0.2 ships in 4 weeks").

Why this works:
- The PRD never blocks shipping. Build v0.1 against the v0.1 doc.
- Future phases ship only when a concrete need lands — no speculative complexity.
- The PRD stays the architectural contract so each future axis composes cleanly when added.
- The v0.1 doc gives the user something to react to without forcing them to absorb the full vision.

### When to use this pattern

The spec is big enough that:
- It has multiple independent axes ("harness × host × agent × context" — 4 axes).
- A phased rollout is necessary (v0.1 → v0.2 → … → Phase 5).
- Some phases are speculative ("build only when needed"); others are buildable now.

If the spec is small (one component, one obvious shape, two days of work), skip this — write one PRD and hand it to `prd-plan`.

### The "first edit to the LIVE/shared path is its own version + its own review" roadmap discipline

When a capability is built but not yet *wired into the path users actually traverse* (a new sink behind
the live ingest, a new provider behind the live checkout, a new model behind the live router), make that
wiring **its own roadmap row with its own review pass** — do NOT fold it into the version that built the
capability. The pattern that works (proven 2026-06-15, NotebookLM sink selector): v0.2 builds the adapter
+ a selector seam *that nothing live calls yet* (provably no-op, zero blast radius); **v0.3 is the first
intentional edit to the live pipeline and gets its own PRD + Opus passes.** Why this is worth a separate
cut: the moment you route a real caller through the new path, the blast radius jumps from "isolated new
code" to "every existing cron/skill/habit that uses this surface" — that risk class deserves its own
invariant set (esp. **"the default is unchanged for every existing caller"** as a hard, grep-gated
invariant) and its own review, not a footnote in the build PR.

- **Make "I never changed the default" a first-class invariant with a closeout grep.** The dominant risk
  of wiring a parallel backend is a silent default-flip. Encode it: "every surface called with no
  sink/provider arg routes to the OLD default; behavior byte-identical." Prove it with per-surface
  default-branch tests + a `grep` that no live caller hardcodes the new backend.
- **Pair the live-cutover version with a Phase-0 probe BEFORE any wiring.** A live API probe routinely
  falsifies a spec assumption the wiring depends on (this session: the `/api/sources` LIST omits the
  per-source `notebooks` membership field that scoping needs — only the per-source DETAIL carries it; and
  the answer API wants a model *id*, not the model *name*). Run the cheap probe, record the result in the
  PRD status, and correct the design to ground truth before writing the integration — same discipline as
  the Phase-0-falsifies-the-UI-flow pitfall below, applied to an API contract.
- **One routing chokepoint, grep-gated (I6-style).** The cutover's job is to make every live caller go
  through ONE selector and leave NO direct calls to the old impl — `grep` for `oldimpl.method(` returning
  only the selector + the impl is the closeout proof that the choice is real and not half-wired.



### Delivery & doc shapes (always dual-format)

**Dual-format delivery follows the canonical rule in `prd-share` — load it with `skill_view(name='prd-share', file_path='SKILL.md')` → "The delivery rule (canonical)" section; do not restate it here.** In short: present a PRD in chat as a live HTML link via `prd-share`; save the PRD as Markdown in the project's `docs/` (and Obsidian too, as `.md`, if asked). The `.md` is the source-of-truth; regenerate the HTML link from it whenever you re-share.

**Full PRD top section** must include:
- Versioned phase roadmap table: `| Version | What ships | Trigger | Maps to PRD §N phase |`
- A "Resolved Decisions" section capturing Q&A from the planning conversation
- A "Future features, not version-pinned" subsection for things that aren't on the version ladder but should ship someday

**Agent/fleet migration PRDs** should also include a historical-memory track when moving between harnesses, hosts, or long-lived agents. Explicitly cover: raw/reference session archive vs curated shared memory (do not auto-inject raw transcripts into prompts); session store inventory for old and new harnesses; retention/privacy/redaction rules; where shared memory lives (mem0 / Obsidian-backed notes); and smoke tests proving at least one old session can be found/summarized and a curated decision read by the new agents.

**v0.1 implementation cut** must include:
- A prominent header pointing back to the PRD (with rendered URL when available)
- A bulleted "v0.1 explicitly does NOT do" section so the scope boundary is unambiguous
- A forward-compatible dispatch/API contract — the function signature should already accept v0.2+ args, with no-op defaults or `NotImplementedError`-style errors, so adding axes later doesn't break the API
- A 6-8 item failure-mode table with explicit countermeasures (the "I never use this" list)
- A concrete implementation plan handed to `prd-plan`, with a smoke-test step (not optional)

Cross-link both docs explicitly. When one updates, link the other. Share rendered HTML links via `doc-share` (here.now) when presenting either doc in chat — see "Delivery & doc shapes" above. The bite-sized step breakdown of the v0.1 cut is `prd-plan`'s job — including the **smoke-test-as-a-step** rule (end-to-end invoke the real thing before commit).

## Per-phase Verification block

Every implementation phase must end with a concrete Verification block:

```markdown
- **Phase N — [name].** [what ships]
  - *Unit/script check:* [narrow failing/pass check]
  - *E2E/integration check:* [real input on the real path] OR `Not applicable: [one-line reason]`
  - *Negative/adversarial:* [bad input / trust-boundary case] OR `Not applicable: [one-line reason]`
  - *Evals (if ML/heuristic/model):* [metric + target + dataset/sample]
  - *Verify with:* `[exact command]` → expected result
```

Rules:

- If the phase changes routing, persistence, external process spawning, network calls, GPU/model inference, isolation, health, rollout, or any user-facing path, the e2e check is required.
- If the phase touches auth, secrets, filesystem boundaries, tenant/session isolation, public posting/sending, or destructive operations, a negative/adversarial case is required.
- For ML/model/heuristic work, tests are not enough. Add evals: quality target, latency/cost budget, regression delta, and representative sample/corpus.
- Do not write "verify it works." Name the command, input, and expected output.

## Testing vs evals

- **Tests** answer: did the code do the required thing? They are pass/fail.
- **Evals** answer: did the system do it *well enough*? They measure quality/behavior (accuracy, recall, latency, cost, preference fit, WER, win-rate, etc.).

Use both when behavior is probabilistic, model-mediated, preference-scored, or retrieval-ranked.

### Live-agent recall / context-engine eval gates

When a PRD's load-bearing claim is that a live model will recover compacted/retrieved context (LCM/DAG context engines, memory recall, retrieval tools, summarization-with-expand, etc.), do **not** accept a tiny scripted smoke as the promotion gate. A smoke can prove mechanics (tool exists, expand returns bytes); it does not prove the live agent reliably uses the tool.

Spec the gate as a statistical eval:

- Fix sampling params where possible (temperature 0; seed if exposed), shuffle fixtures, and ensure trials are independent.
- Gate on a confidence interval, not just a point estimate. Name the method (e.g. Wilson 95% lower bound) and make it binding: point-pass/lower-bound-fail is a NO-GO.
- Pin a concrete N that actually clears the CI floor at the target rate; don't write `N≥20` theater for a 0.95 claim.
- Define false/confident-wrong operationally. Exact sentinel arms should use deterministic string/byte checks; semantic arms need a judge rubric, planted calibration set, judge precision/recall targets, and manual spot review sized as a function of N.
- Include negative trials for nonexistent facts and ambiguous prompts; a hedged/not-found answer is a miss, not a confident-wrong.
- Print the observed counts, CI, and per-arm breakdown in the report so closeout can catch a weak category hidden by a green aggregate.

For context engines that persist raw conversation/message data, the PRD must also include data-at-rest gates before high-blast-radius rollout: file permissions, encryption or explicit risk acceptance, retention/TTL, redaction corpus over raw store *and* index/FTS surfaces, fail-open degraded telemetry, over-limit terminal behavior (fallback/abort), and config/artifact hash pinning between pilot and production agents.

For an **objective acceptance GATE over a scorer/ranker/classifier/ORACLE** (gold sets, eval
fixtures, "model labels → code scores" pipelines, and compression/transform benchmarks whose
oracle decides PASS/FAIL), load `references/gold-set-eval-gates.md` — the recurring traps:
gold items missing the model's input labels → everything coerces; ideal-labels-not-model-run
invariant; assert on SCORE not placement; — for a **DEMOTION-GUARD / new-backstop over a
label-driven POOL** (a junk/spam/off-topic down-ranker that overrides the model's label): the
train==test precision-gate trap (tune on day-1, gate on a HELD-OUT day-2 + full-clean-set
independent labeling), downgrade-only-BY-CONSTRUCTION (a monotonic clamp as the LAST op, not a
per-pool property test), byte-stability-vs-POOL-MEAN-coupling (per-item terms byte-identical but
slot-scoped for the PF-coupled field), shape-detector FALSE-POSITIVE magnets (lone `$TICKER`
nukes `$NVDA`; `FREE…API` nukes real credit programs → require the SHAPE + a mandatory legit
near-miss; foreign by SCRIPT-CLASS not byte-ratio), and a live-proof that fires on a `core`-labeled
item + a demotion-RATE watchdog; **mutation-matrix one-per-bar-in-its-own-subprocess,
and the mutation set must be a committed `mutations(task,raw)` ENUMERATOR (mechanical,
field-wise confusables from the source), never an author-hand-listed set of strings**; gate-pin
to a single literal; name the structurally-satisfied bars;
the D-8 rule (prove on proposed labels BEFORE ratification, SURFACE a failure as an owner decision, never relabel-to-green); and
— for a SUBJECTIVE "is this TRUE about the user" gate (user-model/personalization conclusions): the
groundedness-vs-truth two-arm split (LLM judges groundedness, only the human/delegated-oracle judges
truth), the small-N-can't-power-an-LB trap (need n~80-100, a perfect 11/11 is only LB 0.74), the
system-fact/one-off-relabeled-as-user-decision overclaim class fixed by iterative prompt attribution
discipline, and grading-honestly-as-the-delegated-oracle (don't fudge a 0.836 strict-LB to green); and
— for transform/compression benchmarks — the **baseline-fairness gate FIRST** (test the
uncompressed baseline on the same corpus before measuring the transform), the **realistic-vs-
adversarial OPERATING POINT** trap (a "X fails" verdict computed at a correctness-fixture's forced
worst-case operating point is a worst-case verdict, not THE verdict — compute the break-even/crossover,
re-derive gate constants from the corpus under test, use conservative CI bounds, and treat the measured
frequency as model-specific), the **uniform-oracle-loosening ratchet** (normalizing a trust-root oracle
to rescue one contender relaxes it for ALL — report each already-certified arm's old-vs-new delta and
gate the trust-root review BEFORE the measurement spend), the **measurement-instrument trust root** (the
expand/usage-detection ADAPTER fabricates the datapoint if buggy — senior review + your own adversarial
probe before spend, AC6 git-DAG; the wrapped-shell + interpreter-glued-relative false-negative class),
the **pass-1 measurement-honesty triad** (in-sample-fit break-even → pre-register the cost model;
N-too-small → Phase-0 MDE + INCONCLUSIVE branch; grep≠runtime-isolation → out-of-band process/socket +
egress-allowlist), the **eligibility
triage** when it blocks (format-variant/citation/ambiguous = fix; flakiness/genuine-model-miss
= EXCLUDE, never loosen), editing the corpus **SOURCE-builder not the regenerated JSON+manifest**,
and **non-author certification** of a trust-root oracle loosening (separation of duties).

## Acceptance criteria

Each acceptance criterion must be objectively checkable and trace to a phase's Verification block:

```markdown
- [ ] Search finds a saved X video by spoken phrase from its transcript. Evidence: `pytest ...::test_transcribe_x_video_end_to_end` passes and manual query returns tweet ID X.
```

Avoid criteria like "system is robust" or "documentation is good" unless paired with a concrete evidence source.

**Optional EARS notation:** If trigger/response wording makes the criterion clearer, you may use EARS (Easy Approach to Requirements Syntax). This is optional, not a required format.

```markdown
- [ ] WHEN <trigger> the system SHALL <response>. Evidence: `[exact command/check]` shows [expected result].
```

Use EARS for event-driven or state-dependent behavior. Skip it when a plain evidence-backed checklist item is clearer.

## Review handoff

When the PRD is drafted:

1. Run `prd-review-pipeline` for the requested number of passes. Remember: one pass = review + fix.
2. If the PRD needs parallel implementation, use `prd-swarm-plan` after review approval.
3. If the PRD needs step-by-step implementation planning, use `prd-plan` on approved phases.
4. Finish with `prd-closeout` before declaring done.

## Common pitfalls

- **A "zero-maintenance auto-derive" can be DERIVING FROM A PROXY FIELD that isn't the value's source of truth — ground-truth the derive against the FULL set + any existing curated truth BEFORE speccing it (2026-06-29).** A seductive simplification in a directory/dashboard/inventory spec is "auto-populate column X from field Y so it self-maintains" (owner from an IP, type from a path, team from a repo prefix). The trap: field Y is often a **front-door / proxy / index artifact**, not where X actually comes from — so the derive is *plausible-but-wrong* for the majority, and "self-maintaining" is illusory because every correct value still needs a hand override. Worked case: a spec derived `index.ace` **owner from the AGH answer-IP**; but the answer-IP is the reverse-proxy target (`.216` = the the Linux GPU box Caddy that *fronts* the media PC's tdarr, homelab's portainer, etc.), not the owning host — so it conflicted with the already-curated owners on **10 of 16** known names (Opus pass-1 BLOCK; verified independently). The author had sampled 4 happy-path names and over-generalized. **The discipline, at spec-authoring time:** (1) before writing the derive as a Resolved Decision, run it over the **whole live set** and diff it against any **existing curated/ground-truth values** — a non-trivial conflict count kills the derive; (2) name what field Y *actually is* (a proxy/index/cache target) vs what X *is* (the real owning entity) — if they're different layers, the derive is wrong by construction; (3) the honest fallback is usually **curate once + drop the false "self-maintaining" claim** (reframe to "auto-*discovery* is preserved, auto-*metadata* is curated"), which is also *simpler to build* (no derive code, no threading, no fallback edge). This is the falsified-premise STOP applied to a *derivation mechanism*: a premise about where a value comes from is checkable with one query over the live data — check it before the design, not after the BLOCK.
  - **The matching BUILD-side guard: a 100%-populated arity gate ("43/43 non-blank") does NOT catch a wrong-but-non-blank value — add a GOLD-SET correctness assert seeded with the exact names the killed derive got wrong.** After redesigning owner-by-IP → curated, the v1 acceptance was "43/43 entries have a non-blank owner" — which passes green even if a curation typo re-introduces `tdarr→the Linux GPU box` (the original error). Pass-2 flagged it; the fix is a small gold set asserting the *correct* value for the known-conflict names (`tdarr→the media PC`, an the orchestrator agent portal→`the orchestrator agent`, `udm/router→UniFi`) so the prod-wrong-but-demo-green trap can't survive at reduced amplitude. General rule: when a spec replaces a falsified auto-derive with curation, the closeout gate must assert *correctness on the former-failure cases*, not just non-emptiness.

- **An "acceptable fail-quiet / acceptable degradation" disposition is a WEAK default this user rejects — a reviewer (human OR bot) will rightly challenge it, and the proper fix is usually tiny (2026-06-25).** When a spec hits an edge where the feature silently does *less* than promised (a notice that won't fire, a value that goes stale, a path that no-ops), the lazy move is to write it into §8 Risks as "acceptable fail-quiet, documented" and move on. For a user who **rejects "good enough / self-heals / fixes-next-run" framings** (see USER profile), that disposition is a latent BLOCK: a code reviewer — or an automated reviewer like Greptile — will re-raise it as a real defect, and they're usually right. Worked example: a session-reset-notice spec dispositioned the "compaction zeroes `last_prompt_tokens` → a compressed-then-idle session goes un-announced" edge as "acceptable fail-quiet." Greptile flagged it as a P2 ("session WITH history silently suppressed"), and the *correct* fix was a ~10-line durable `had_any_turn` latch (set on first real turn, never zeroed by compaction) — small, clean, and RED-provable. **The discipline:** before parking an edge as "acceptable degradation," ask "is the *proper* fix actually small?" If yes (a durable flag, a tri-state, a separate signal), BUILD it — don't disposition it away. Reserve "acceptable fail-quiet" for edges whose proper fix is genuinely disproportionate (e.g. the 90-day-prune-deletes-the-row case, where the entry is gone and there's structurally nothing to notify from). And when a bot/reviewer re-raises a degradation you already "considered" in the spec, the move is **implement the proper fix and resolve the thread on merit** — NOT reply "already considered, working as intended." (Companion to the "fix everything ≠ license to include impossible work" pitfall above: that one keeps *impossible* inclusions out; this one keeps *cheap-but-skipped* fixes IN.)

- **"Fix everything / boil the ocean / do it all" is NOT a license to include structurally-impossible
  or invariant-violating work — ground-truth the slices and scope the impossible ones as explicit
  Non-Goals (2026-06-20).** When the user says "fix everything" / "close the whole gap," the lazy read
  is to write a spec that promises to close 100% of the visible deficit. But a real gap is usually
  heterogeneous: some slices are tractable, and some are **structurally unfixable or would violate an
  invariant** (e.g. backfilling Instacart per-line prices when the source data has NO per-line price —
  fabricating one breaks the money "missing beats wrong" Constitution). The honest move is to
  **measure the gap, split it by tractability, and make the impossible/invariant-violating slice a
  named Non-Goal with the reason** — do NOT let "everything" silently sweep it in, and do NOT promise
  a number you can only hit by guessing. Same for the success bar: when part of the tractable work
  *correctly* fails a gate (penny-discount orders that don't reconcile), the target is "every item
  that CAN pass, does" + an **honest classified residual**, never zero. Put the measured split in the
  Ground-Truth section, the impossible slice in Non-Goals with its one-line reason, and the residual
  bar in Resolved Decisions. (Same family as the simplicity gate, inverted: the simplicity gate keeps
  speculative *additions* out; this keeps impossible *inclusions* out of an over-broad verbal ask.)
- **A "derive Y from key X" design must validate X across the FULL set AND cross-check against any EXISTING curated truth — a key that looks like the identity is often an INDIRECTION/proxy for it (2026-06-29).** When a spec proposes auto-deriving a field (owner, type, category, tenant) from some observable key (an IP, a path, a hostname, a port, a label), the seductive failure is to sample 3-4 *happy-path* entries, see the derive "work," and write it as a confident Resolved Decision — then a review (or production) finds the key is a **proxy/indirection layer, not the thing itself**, so it's plausible-but-wrong for the majority. Worked example (BLOCKed by Opus pass-1): "derive index.ace OWNER from the AGH answer-IP." Sampling audiobooks/cron/jellyfin made it look clean — but the answer-IP is the **reverse-proxy/DNS front-door target**, not the owning host: one Caddy box (`.216`) fronts ~78% of names regardless of what actually runs them, so it labels the whole index "the Linux GPU box"; `.18` (Mac Studio's Caddy) labels the orchestrator agent-owned portals "Mac Studio"; `.4` (the HA frontdoor) labels UniFi's udm/router "HAOS." Cross-checked against the spec's OWN already-curated overlay: **10 of 16 known names conflicted.** The "self-maintaining" headline was illusory because every correct value still needed a hand override — the exact per-entry curation the auto-derive claimed to eliminate. **The discipline, at authoring time (cheap, before the review BLOCK):** (1) run the derive over the *entire* live set, not a sample, and print the output distribution — a histogram that collapses to one value for most rows (`.216`×36 → "the Linux GPU box"×36) is the tell that the key is an indirection, not the identity; (2) if ANY curated/gold truth for that field already exists (an overlay, a manual map, prior labels), **cross-check derived-vs-curated and count conflicts** — a high conflict rate falsifies the premise outright; (3) ask explicitly "is this key the THING, or a layer in FRONT of the thing?" (an IP behind a shared proxy, a path behind a symlink, a port behind a router) — front-door/proxy/alias keys derive the *front door's* identity, not the backend's. If it's an indirection, the honest design is usually: keep the field curated (the existing curated set is already correct), drop the false auto-derive goal, and accept blank-until-curated for new entries — OR derive from a source that actually encodes the identity (and prove its conflict count is ~0 across the full set, not a sample). This is the same family as the next bullet, but the trigger is a *derive/lookup key* specifically, and the cheapest catch is the full-set histogram + the conflict count against existing truth.

- **Ground-truth the live system with measured queries BEFORE choosing the architecture — a wrong
  assumption about overlap/coverage picks the wrong design.** A "do we also need to do X?" question
  (e.g. "does the price re-walk also populate the missing images?") is answerable with a cheap live
  query, and the answer routinely flips the architecture. Measured example: the price walk visits only
  *unpriced orders*, but 784 of 824 missing images lived in *already-priced* orders → the price walk
  would fix only 40, so images MUST be a separate pass. Run the count, put the numbers in a
  Ground-Truth table at the top of the spec, and let the measured split (not an assumption) decide
  whether work is one job or two. (Composes with the Phase-0-probe-falsifies-the-architecture rule:
  same discipline, applied at spec-authoring time with a SQL/count query instead of an API probe.)

- **Asserted-invariant trap: prove the real capability boundary, not the wording.** For specs that claim "only one LLM/tool/path," "provider retired," "no live actuation," "gate before egress," or "behavior-preserving rename," write the closeout proof at the substrate/capability level. Static grep, inherited tests on an old call site, one happy-path utterance, or a `dry_run=True` flag honored by the live executor are proxy greens. Preferred proof patterns: a null/raising dependency injected into the actual production-path executor; an out-of-band process-boundary spy over the full corpus (not one case); a mock/non-live client where real actuation capability is absent; egress redaction spies over every outbound surface (LLM, post-tool narration, fleet handoff, bridge/search calls); golden sweeps that include both output JSON and dispatch branch; and filesystem-write guards for read-only audits. If a pass-2 review returns non-blocking tightenings, fold them into the PRD before marking APPROVED so they become implementation requirements, not reviewer footnotes.
  - **The THEATER-INVARIANT sub-trap: a guard that recomputes its checked value from an input the guard's own code path can't mutate cannot catch the risk it names — it passes by construction (2026-06-26).** Distinct from the proxy-green above (proving at the wrong layer): here the invariant is *structurally incapable of failing for the risk it's written against*, so it's a green that guards nothing. Worked case: a respec loop's INV-8 hash-chain check (`new_spec.seed_text_hash == approved_hash`) was cited as the guard against the rewritten spec **drifting from the approved idea** — but the adapter recomputes that hash from the UNCHANGED seed (`hash(seed.title+summary+detail)`), so it ALWAYS matches no matter what the LLM wrote in the spec *body*. The hash binds the seed record; idea-drift lives in the prose the hash never sees. An Opus pass-1 BLOCKed it correctly. **The tell:** ask of every invariant "what concrete bad input makes this check FAIL?" — if you can't name one because the checked value is derived from something the actor in question never touches, the invariant is theater. **The fix is honesty, not a bigger hash:** keep the real (narrow) guarantee with its true scope ("C1 catches seed-RECORD tampering only"), then name the *actual* guard for the real risk as a separate invariant — here C5 = the independent re-review (the same adversarial reviewer sees the new body) + a hardened worker prompt ("do not change the idea; keep title+summary verbatim"), proven by a grep that the prompt carries the constraint, NOT by the hash. Don't let a true-but-irrelevant check stand in for a missing real one.

- **Before editing or status-reporting on a PRD, GROUND-TRUTH the live file + the build — your context may be stale across compaction.** A multi-turn spec session compacts; the summary you carry can be many versions behind the file on disk and the actual built artifacts. Symptom (real own-goal, 2026-06-12): I confidently edited a PRD as a `v1.2→v1.3` transition — adding a Resolved Decision, rewriting the v0.1 cut, adding Phase tests — while the **live file was already `v1.4`, the review passes already run, and the system already built, shipped, and running its first nights** (the EXPERIMENT/state file showed `phase: observing, nights_elapsed: 1`). My edits duplicated work already present in better form and risked clobbering a finalized doc. **The reflex:** when you resume work on an existing PRD/spec, BEFORE the first edit (a) re-read the file's status/version header, (b) `search_files` the project dir for already-built artifacts (`lib/`, a profile/config, an `EXPERIMENT`/state/`DEPLOYMENT-NOTES` file, the review dir's verdict files), and (c) if a `read_file` returns `dedup: file unchanged since last read`, that's positive evidence you already saw it this lineage — trust it, don't re-derive. A status claim ("we still need to review/build X") is checkable in seconds; check it. If the file is ahead of your assumptions, STOP and reconcile out loud ("I was working from a stale view; here's the real state") rather than continuing to edit — and do NOT overwrite a later version header with an earlier one. (Same family as `fleet-lane-ownership-routing`'s "don't assert project status from a stale compaction summary — check the repo.")
  - **The single highest-risk moment for this trap is a GATEWAY-RESTART or COMPACTION HANDOFF banner** ("your previous turn was interrupted by a gateway shutdown", "[CONTEXT COMPACTION — REFERENCE ONLY]"). Those banners make a mid-flight project read like a *fresh* request, so you answer the user's new ask ("add X to the spec", "make decision Y") as if X/Y were undone — when in fact they were already resolved several commits ago, in better form. Re-confirmed own-goal (2026-06-13): after a gateway-restart banner I re-added an Undo section (`§4a`) and re-stated an arrow-key decision that were ALREADY in the live file as `§0.5 D-1/D-2/D-3` + `§8.5` at v1.3, two review passes deep, with the build already underway (untracked `undo.ts`/`keymap.ts`/`deletable.ts`). **The reflex, made mechanical:** the first action after ANY restart/compaction banner on a code/spec project is a ground-truth read, NOT an edit. In a git repo this is two commands and ~3 seconds: `git log --oneline -8 -- <the spec file>` (shows the real version lineage + that review passes ran) and `git status --short` (untracked source/test files = the project is past spec, into implementation). Only after that do you act on the user's ask. If they reveal the ask is already done, say so plainly and pivot to *verifying* it (run the gate, dogfood) — that is what the user actually wants next. If you already made a duplicate edit before checking, `git checkout -- <file>` to revert cleanly rather than trying to reconcile your stale version in.
- **A Phase-0 live probe can FALSIFY the spec's assumed UI flow — correct the implementation to ground
  truth, and scope the still-unverified branch as a DOCUMENTED FAIL-CLOSED limitation rather than
  over-claiming.** When a spec for a browser/UI-driving feature assumes a specific interaction flow (e.g.
  "select 'Other', type 0 in the custom field, blur to commit"), the live Phase-0 probe is where that
  premise gets tested — and it often turns out wrong (real Instacart flow: clicking "Other" opens a modal
  with a dedicated **"Continue with $0 tip"** button; the typed-0-field path didn't commit at all). Two
  moves: (1) **correct the built code to the proven live flow** (record the correction in the spec status +
  probe notes so it's not re-derived), and (2) when one sub-branch (here: an arbitrary non-preset custom
  amount, whose modal sub-flow was stateful and didn't reliably surface) can't be proven live, DON'T claim
  it works — implement it best-effort, confirm it **FAILS CLOSED** (the guard never overspends / never
  takes the wrong action when the commit doesn't land), and ship it as an explicit "known limitation:
  fail-closed, resolve with a focused follow-up probe when actually needed" in both the spec and the
  overview doc. The load-bearing case (the user's default) being live-proven + a fail-closed edge is an
  honest, shippable outcome; a green unit suite over the unverified flow is not. (Same family as the
  prd-review-pipeline "verify the load-bearing claim empirically; APPROVE+unproven-premise = HOLD" rule,
  applied to the BUILD: prove the real path, scope what you couldn't.)
- **The Phase-0 probe can falsify the spec's whole ARCHITECTURE / integration-substrate — not just a UI
  flow or an API field — and when it does, the win is collapsing risk surfaces, not just fixing a step
  (2026-06-17, headroom economics Amend-4).** A spec's risk model (and the Opus passes that hardened it)
  is built on an *assumed integration shape*. If that shape is wrong, whole invariants/ACs evaporate. Here
  the PRD + two Opus passes assumed `headroom` was a **network PROXY in front of the provider** — which
  drove a usage-through-proxy BLOCKER, an egress-allowlist invariant, a B3 runtime-isolation gate
  (out-of-band process/socket check), and a reasoning-token-zeroing probe. The ~7-call Phase-0 probe
  ground-truthed the actual library surface: headroom 0.25.0 runs in **library mode** (a jailed subprocess
  content-compressor; `compress()` returns a view + a `hash=` retrieval marker), and the model call goes
  through the *already-trust-root-signed* CodexExecClient seam, which returns real per-turn usage
  **directly** — headroom never mediates the provider call. So all four proxy-shaped gates became **N/A**
  (no proxy → no listener → no egress actor → usage fidelity == the signed seam's). A second assumption
  fell the same way: the spec carried "lossy AND CCR modes," but `compress()` has **no ccr/lossy switch**
  in library mode (`headroom.ccr` is a live-MCP mechanism, out of scope) → CCR dropped to lossy-only,
  OQ3 answered honestly. **The reflex:** the FIRST thing a build phase does is a cheap probe of the real
  integration substrate (import the library and read its actual surface; compress one real corpus item;
  check what the call path *actually* returns) BEFORE writing the adapter or trusting the risk model. When
  it falsifies the architecture, (a) write a prominent "PHASE-0 GROUND-TRUTH CORRECTION" block in the spec
  status naming each gate that is now N/A and why, (b) bump the version with the correction folded, (c)
  keep the honesty-discipline gates that are *architecture-independent* (cost-model freeze, power/MDE +
  INCONCLUSIVE branch, correctness-LB veto — these still stand), and (d) don't mourn the deleted gates:
  a smaller true risk surface is the probe doing its job, not wasted review. The cheapest dollar in the
  whole build is the probe that deletes three invariants you'd otherwise implement and test.
- **A passed REVIEW can still rest on a FALSE PREMISE — the cheap ground-truth probe of the live state belongs in the spec, not after a BLOCK (2026-06-22).** A senior/Opus review validates a spec's internal coherence, risk hardening, and invariant framing — it does NOT validate whether the spec's *motivating factual premise is true*, because the reviewer reads the spec, not the live system. Two premises sank a v0.1 cron-lifecycle PRD that was otherwise well-framed, and BOTH were a 2-command live probe away: (1) the spec said an ingest job's "dead remnants" justified an auto-retire-on-complete check — but reading the live manifest showed the 2 remnants were `fail_kind=transient` (a bot-gate + an empty-ASR, both **recoverable**), so the completion check would return False *forever* and never fire on its own motivating incident; making it fire would require mis-classifying recoverable items as terminal (violating the asymmetry rule). (2) the spec assumed the cron's respawn was driven by an exit-code contract — but reading the actual plist showed pure `KeepAlive:SuccessfulExit:false` with the wrapper already exiting `rc=0`, so the entire exit-code-signal mechanism was solving the wrong problem. **Rule: for any spec whose load-bearing premise is a claim about live state (an item's terminal-vs-recoverable classification, what a cron's respawn driver actually is, whether a corpus is "done", what a config file actually contains), GROUND-TRUTH IT IN THE SPEC with the cheap probe (`cat manifest.json | jq`, `plutil -p the.plist`, the live `ps`/`pgrep`) and put the result in a "Ground-Truth" block at the top — BEFORE writing the design.** The tell you skipped it: the review's verdict turns on a question the spec asserts but never measured ("are these remnants terminal or recoverable?"), and answering it flips or kills the whole approach. This is the `Phase-0-probe-falsifies-the-architecture` rule applied at *authoring* time with a filesystem/CLI read instead of an API probe — and it's cheaper to do before the review than to absorb a BLOCK and rewrite. When a probe DOES kill the premise, the deliverable is the honest reframe + the cheaper correct fix, not a v2 that defends the dead design.
  - **The OBSERVABILITY/WATCHER variant: a monitor's premise IS "the signal it watches isn't already firing" — grep the live source the watcher will read, BEFORE designing it (2026-06-22).** When the spec is a watcher/digest/alert cron whose design rests on "a healthy system emits ZERO of these → silent until a real event," that "healthy → zero" is a measurable premise about the live system, and it is wrong often enough that the FIRST line of the Ground-Truth block must be the literal grep: `grep -c "<MARKER>" <the actual log(s) the watcher reads>` across every source (e.g. all profile gateway logs). A non-zero count means the watcher is downstream of a *currently-firing fault* — root-cause THAT first; a monitor for a live bug (possibly a regression from your own recent PR) is a distraction until the bug is understood. The compounding own-goal: such specs default to **silent-forward** (first run sets the read offset to EOF so it "doesn't dump history"), which on a system that's *already firing* **buries the live backlog on adoption day** — you ship a detector that, on the one day it has something to say, says nothing by design. (Caught by an Opus review that grepped the orchestrator agent's `gateway.log` and found 4 `COMPACTION_STATS_RECONCILE_FAILED` warnings dated the spec's own authoring day, some after the latest restart.) The tell: a `test_first_run_silent_forward` that asserts "first run over a log already containing markers emits nothing" — that test is encoding the bug, not the feature. Full watcher-design discipline (rename-rotation, multi-line records, detector-of-the-detector liveness, cross-profile content-echo safety) lives in `cron-alert-discipline` → "Before you build a marker/log WATCHER".
- **A red in a live E2E/dogfood after a UI change is often a STALE TEST SELECTOR, not an app regression — prove which, don't wave it away.** When a feature cut renames or reorders UI (e.g. a toolbar button `+ Note` → `Note`, new sibling buttons shifting `:nth-of-type` positions), the existing dogfood script's hard-coded selectors silently miss their target, so the click never lands and the assertion fails — looking like a real bug. Before either (a) "fixing" the app or (b) dismissing the red, **read the failing check's selector and compare it to the current DOM/markup.** If the behavior is actually present (the class/handler exists, other entry points work) but the test's selector is outdated, the honest fix is to **update the test to the current UI and re-run to true green**, recorded as a `test(e2e):` commit — NOT to assert "stale test, ignore it." Two recurring sub-causes seen together (2026-06-13): a renamed/moved button (fix: match by trimmed exact text, not position), and a **transient-status race** — an action sets a status string that a periodic refresh poll overwrites before the test's single delayed read (fix: sample in a tight loop right after the action and assert the status appeared *at any point*, rather than one `sleep(N)` then read). A green you re-proved after fixing the selector is trustworthy; a red you talked past is not.
- **Mock trap:** mocked seams prove the mock, not the integration. Include at least one no-mock seam/e2e where interfaces meet.
- **Rubber-stamp acceptance:** if an acceptance criterion cannot name evidence, rewrite it.
- **Overlap with implementation plans:** do not turn the PRD into 50 tiny TDD steps. Stop at phase-level verification; `prd-plan` handles bite-sized tasks.
- **Smuggling a behavioral change into a "refactor"/"no behavior change" spec.** When a PRD is framed as a pure refactor / cleanup / DRY-consolidation (its Goal and Non-Goals promise "meaning unchanged, no new capability") but the user's ask actually adds **one** behavioral change, do NOT let it ride under the refactor framing — that quietly breaks the spec's own contract and the reviewer/closeout can't tell which edits are safe relocations vs real behavior changes. Surface it explicitly, in three places: (1) its own **Resolved Decision** (`D-N`) naming it as the agreed behavioral delta; (2) a dedicated **design subsection** describing exactly what changes and, critically, **what does NOT change (the guardrails)** — e.g. "this gate keeps its teeth," "the work still lives in skill X, this just orchestrates"; (3) a **Non-Goal exception line** that says the behavioral change is called out, not smuggled ("Exception (called out, not smuggled): D-N changes X's behavior; everything else is verbatim relocation"). Then add a **negative/adversarial test** in the relevant phase that proves the change did NOT soften an existing guarantee (e.g. grep that the BLOCK/gate language survived the reword), plus an **invariant** stating the guarantee still holds. One intentional, fenced behavioral delta is fine; an unmarked one in a "refactor" is a latent contract violation.
- **"Enforced" must name a mechanism the agent can't author around — not a prompt/contract it's asked to obey.** When a spec governs what an autonomous run MAY/MUST-NOT do (no push/merge/delete, no write outside a sandbox, a budget hard-stop, a kill-switch), an Opus reviewer WILL block on any invariant that says "enforced" but only specifies a prompt, a `CONTRACT.md`, or a self-logged "REFUSED." The capability must be *absent* (the tool/cred isn't in the profile's toolset — e.g. the native `terminal`/`execute_code` tools are removed and replaced by a restricted wrapper so there's no raw-shell fallback; no git-write token exists) OR *intercepted by a pre-execution layer the model can't rewrite* (a path-guard on `write_file`, an OS sandbox that returns a real `EPERM`, a cron-wrapper preflight that runs BEFORE the agent starts). Corollaries the review pass reliably demands: (1) every "enforced"/"guard" claim names its concrete layer (config key / removed tool / wrapper / OS sandbox) in a mechanism table; (2) the negative test proves **substrate-level refusal** — an *externally-originated* failure (GitHub API rejection, filesystem `EPERM`, missing-cred auth failure) asserted by an **out-of-band checker** (a separate script inspecting external state: branch has no new commit, file absent), NEVER the run's own "I refused" log line; (3) don't make a wrapper *parse arbitrary shell* for write targets (losing arms race — `python -c`, `tee`, `dd`, subshell redirects) — make it a coarse `argv[0]` allow-list and let an OS sandbox confine writes; (4) a deprecated/fragile platform primitive (macOS `sandbox-exec`/seatbelt) cited as a control must be *proven to compile-and-deny* in a test or demoted to defense-in-depth. Watch the second-order trap: a *fix* that introduces a new "enforced" claim ("the wrapper blocks it") is itself asserted-not-proven until its own mechanism + substrate test exist — pass-2 of a review reliably catches these fix-introduced claims.
- **Output unit = cheap-to-skim seed, not merge-ready deliverable, when the worry is review-burden inversion.** For any "agent produces work product the human reviews" system (nightly autonomy, proactive agents, batch generators), the dominant failure mode is *review-burden inversion* — the human spends more time triaging output than the work saved. The design cure is reframing the unit of output as a **seed** (a self-contained spike / researched brief / evidence-backed probe that carries ZERO obligation and is skimmable in seconds) rather than a PR that nags to be merged/closed. Bias the spec toward self-containment, low triage cost, and optionality over completeness/mergeability; make the health metric the human's *positive-signal rate*, not output volume; and bound serendipity to one explicit "wildcard" slot rather than letting the whole run be open-ended. (The matching safety rail — PR-draft-only, never auto-merge — is orthogonal: that's the irreversibility guard, the seed framing is the output philosophy.)
- **"Enforced" / "guard" / "sandbox" must name the mechanism the model CANNOT author around — and the negative test must prove SUBSTRATE-level refusal.** When a spec for an autonomous/agentic system claims an invariant is "enforced" (no push/delete, fs-write confined, budget hard-stop, kill-switch), the #1 review blocker is that the enforcement turns out to be *the model choosing not to* — a prompt instruction, a `CONTRACT.md` it loads, or a self-logged "REFUSED" string. That is OWASP LLM06 (excessive agency), not a control. For EACH such invariant, the PRD must name a concrete bypass-proof layer: **capability ABSENT from the toolset/profile** (the tool/cred simply isn't granted — e.g. no `git push` cred, native `terminal` tool *replaced* by a restricted wrapper so there's no raw-shell fallback), **a pre-execution interceptor the agent can't rewrite**, or an **OS-level sandbox** — and that OS layer is only citable as a control once a test shows it *compiling and actually denying* (don't cite deprecated/fragile platform primitives like macOS `sandbox-exec` as primary on faith). The matching negative test must assert **externally-originated** refusal verified by an **out-of-band checker** (a separate script, not the run): a real GitHub API rejection / filesystem `EPERM` / missing-cred auth failure, and the external state (branch has no new commit, the out-of-tree file does not exist) — NEVER the run's own "REFUSED" log line. Also: a wrapper that tries to parse arbitrary shell for write-targets is a losing arms race (`python -c`, `tee`, `dd`, subshell redirects) — spec it as a *coarse argv-0 allow-list + OS write-confinement*, not a shell-parser. Beware too that **a fix can introduce its own asserted-not-proven claim** (the second review pass reliably catches "you replaced an unnamed guard with three named-but-unproven layers") — when you add a mechanism to close a blocker, give it a test in the same edit. (Proven 2026-06-12 across both Opus passes of a nightly-autonomous-agent PRD.)
- **Output-as-seed reframe to defeat review-burden inversion (autonomous/proactive-agent specs).** When a spec has an agent *produce work product autonomously* (overnight PRs, proactive suggestions, generated artifacts), the dominant real failure mode is **review-burden inversion** — the human spends more time triaging output than the work saved — not catastrophe. The design cure, when the user wants it, is to make the unit of output a **SEED** (a self-contained spike / researched brief / evidence-backed probe that is cheap to skim and carries ZERO obligation) rather than a merge-ready deliverable that nags to be merged/closed. Bias the spec toward: self-containment, low triage cost, optionality, a *ranked triage-first* report, a hard cap on items/run sized to review capacity, and a health metric of **positive-response RATE, not output volume**. Pair it with a budgeted "wildcard / 20%" slot for serendipity. (Proven 2026-06-12; grounded in the failed-AI-PR / maintainer-slop-ban literature.)
- **Orchestrate-don't-inline when one step "calls" another.** If a decision makes step A *call/run* step B (instead of bouncing the user to run B), keep B's actual procedure in B — A loads-and-runs it, it does not copy B's body inline. Inlining would re-introduce the very duplication a consolidation PRD exists to kill. State this in the design section ("the work still lives in B; A orchestrates") and back it with a grep-based check that B's procedure text did not leak into A.
- **User points at a slick framework component to "just use this" — decide REPLICATE-THE-UX vs VENDOR-THE-FRAMEWORK; don't reflexively vendor.** When the user links a polished third-party UI component (a shadcn/Radix/Tailwind React widget, a Vue component, an npm package) to drop into the project, first check the project's ACTUAL stack. If the project is a **vanilla/static artifact** (a server-generated single HTML file, an inlined-SVG dashboard, a no-build page), vendoring the component drags in a whole framework + build toolchain (React + Tailwind build + Radix) **for one widget** — which breaks the "self-contained static artifact" invariant the project was built around. The right Resolved Decision is usually **replicate the UX, not the implementation**: the user's real ask is the *interaction design* (e.g. "a dropdown with preset shortcuts + a calendar for custom range"), which is ~150 lines of vanilla JS + your existing primitives, themed to match. Capture this explicitly as a `D-N` ("do NOT vendor X — it's React/Tailwind; our artifact is vanilla static; replicate the presets+calendar UX in ~150 LOC vanilla, themed to our palette; revisit only if we ever move to a React stack"), and put the framework adoption in Non-Goals. (2026-06-14: user linked `date-range-picker-for-shadcn`; vendoring it would have forced a React/Tailwind toolchain onto a vanilla static dashboard. Same family as the user's "external-skill adoption LEAN — vendor doctrine/reference not engines.") Vendor the component wholesale ONLY when the project is *already* on that framework's stack.
- **A self-validating reconciling data structure must measure its buckets INDEPENDENTLY — deriving one as the scalar residual makes its own `validate()` a tautology (the dead-guard trap, 2026-06-22).** When a spec adds/touches a typed object that carries a breakdown and self-checks an identity (`a + b + c == total`, `cleared + folded + kept == pre`, debit==credit, `parts.sum() == whole`), the tempting "clean" implementation — derive one bucket as `total − (others)` — **silently destroys the guard**: the identity then holds *by construction* and `validate()` can never fail again, so the very invariant meant to catch a mis-bucketing is dead code, and an AC of the form "`validate() == True`" becomes meaningless. This is doubly dangerous when the structure's `validate()` is *already the live tripwire* that caught the bug you're fixing (it was, this session — `COMPACTION_STATS_RECONCILE_FAILED`). The rule: **every top-level bucket of a reconciled identity must be measured independently over its own disjoint input set** (`estimator(rows_a)`, `estimator(rows_b)`, …) so the sum is a *real* cross-check that can still fail. Derive-by-subtraction is fine ONLY for a *within-bucket sub-split* whose PARENT was independently measured (e.g. `other_tokens = parent_tokens − tool_tokens` — the parent total is untouched, so the top-level axis stays a genuine check). Encode it as a hard invariant ("no bucket is assigned `total − (...)`; grep the producer to confirm") + a **single-bucket-only negative test** (corrupt ONE bucket's value, assert `validate()` returns False) so the guard's teeth are proven, not assumed. An Opus review pass reliably catches this; if you're the author, catch it first. (Distinct from the circular-oracle trap below — that's about the *test oracle* being the buggy path; this is about the *production validator* self-defeating.)
- **A "live regression oracle" built from RECORDED numbers is a TAUTOLOGY when the fix's own operand is back-derived from them (2026-06-22).** Tempting move for "prove the fix addresses the LIVE failure": take the real failing log line's operands and assert the corrected identity balances on them. But if the fix *changes one operand* and that operand was only ever logged at its BUGGY value, you can't feed the corrected value from the log — so you compute it as `corrected = total − (the other recorded terms)` and then assert `corrected + others == total`, which is `(total − others) + others == total`: **true for any input, fixed or not.** An Opus review will (correctly) BLOCK this as fake-green even though "it uses the real recorded numbers" — real numbers in a tautological identity prove nothing about whether the *recomputed* operand actually lands where the fix claims. The only non-tautological proof **recomputes the changed operand from the real underlying data** (replay the actual failing session / reconstruct the real rows and run the production function over them), not from the other recorded scalars. If the real session can't be reconstructed, say so in closeout and do NOT count the back-derived identity as the live proof — a faithful synthetic that reproduces RED-on-current-code is the honest fallback, and it must be RED-proven (revert the fix → it fails), never a hand-shaped GREEN. (Distinct from the circular-oracle trap below — that's validating against the *buggy function*; this is validating against *recorded scalars* with the decisive term back-solved out.)
- **"This fixes the LIVE bug" must reconcile EVERY observed failure instance, not a convenient subset — the partial-instance trap (2026-06-22).** When the motivating evidence is N real failure observations (N log markers, N crash reports, N failing rows), a root-cause that explains and fixes *some* of them is NOT "the fix" — and quietly claiming it is, is the falsified-premise class one level in. Worked example: 4 live `COMPACTION_STATS_RECONCILE_FAILED` markers; 3 were a *post*-axis bug (root-caused + fixed + RED-proven), but the 4th was a *pre*-axis failure (a 179K-token gap) the post-fix doesn't touch — a structurally **different second bug**. The fix was real and shippable, but "fixes the live reconcile failures" was an over-claim until each marker was individually accounted for. The discipline: **enumerate the observed instances, classify each against your root cause, and for any instance your fix does NOT explain, treat it as a SEPARATE bug — scope it out explicitly (its own investigation), never let "fixes 3 of 4" round up to "fixed."** The tell an Opus reviewer catches: a regression oracle fed "all the live operands" that silently passes the one tuple the root cause can't explain (because it was rigged tautological — see above) — a contradiction between "root cause reproduced both directions" and "all live markers reconcile." Ship the proven subset honestly scoped ("fixes the post-identity failures; the pre-axis 179K gap is a separate tracked bug"), don't bundle an un-root-caused instance into a clean PR. (Companion to the falsified-premise STOP in `prd-closeout`: a premise about live state — here "these 4 failures share one cause" — is checkable per-instance; check it before claiming the class.)
- **A PROCESS-GLOBAL SINGLETON cannot hold PER-AGENT/PER-CALLER config — "the config isn't applied to it" is a category error, not a missing feature (2026-06-27).** When a spec wires a tuning knob (a threshold, a floor, a feature flag) into a component that is a **process-global singleton** (one instance shared by every agent/session/caller in the process — the LCM context engine, a shared client factory, a module-level cache), a reviewer (human OR bot) will reasonably flag "you read `compression.skew_floor` for the built-in per-agent path but the singleton plugin still runs the default." The lazy fix — *mutate the singleton's attribute per-agent at init* — is the actual bug: agent B's init silently overwrites the value agent A is already using. But the *opposite* "fix" (thread a per-caller value through every call) is also wrong for a shared object. **The resolution is to recognize the contradiction: you cannot have BOTH "per-agent override" AND "no shared-state mutation" for a process-global object — they are mutually exclusive.** So pick the coherent one for the deployment: a process has exactly one config file, so the singleton should **source the static tuning constant from its OWN process config ONCE at construction** (e.g. `LCMConfig.from_env()` reads the `compression.<key>`), NOT be mutated by any per-agent caller. Per-agent instances (the built-in compressor is a fresh object per agent) legitimately take the value as a constructor arg; the singleton legitimately reads process config. Both ultimately read the same config block. The part that genuinely IS per-conversation (here: the skew *history* the median is computed from) is the part that resets at session boundaries — keep that distinction explicit in the design. State in the spec, per affected component: *is this object per-agent (constructor arg OK) or process-global singleton (read-own-config-once, never per-agent-mutate)?* — and call out that a per-agent mutation of the singleton is the rejected option, with the prior reviewer thread that rejected it. This is the same family as the asserted-invariant trap (prove the real boundary), applied to config-scoping vs object-lifetime. When a PRD's correctness claim is "the new code path AVOIDS bug B that the old path has," do NOT reconcile the new path's output against the old `build_report(...)` / legacy function as the test oracle — that function still HAS bug B, so for exactly the inputs that exercise B the two will legitimately disagree, and the reconciliation test either fails or gets silently weakened to inputs that dodge B (proving nothing). Split the oracle: for inputs where old and new MUST agree (B doesn't fire), cross-check to the legacy function within an epsilon; for the input that triggers B (the whole point of the fix), cross-check to a **hand-computed fixture expectation with its arithmetic shown inline in the test** — never to the buggy function. Flag that hand-typed value as load-bearing (independently review it; if it's typed wrong, every downstream gate greens on wrong math) and assert the fixture actually exercises B (e.g. the boundary case has data on both sides of the boundary). (2026-06-14, caught by Opus pass-1 of a date-range PRD whose client-side windowing was being reconciled against the same `_cutoff` boundary bug it was meant to dodge.)

- **An "early-stop / I've-seen-this-already" optimization over an ORDERED stream needs N-consecutive evidence + a periodic full-pass safety net — single-hit is unsound under gaps (2026-06-14, caught by Opus pass-1).** When a spec proposes stopping work early because it detected an already-processed item (incremental ingest that stops at the first known record, a sync that halts on the first unchanged row, a crawl that quits at the first seen URL), the naive rule "stop on the first already-known item" is **unsound whenever the local store can have gaps** — a deleted-then-readded record, an item missed by a prior bounded run, an out-of-order arrival. The first known item does NOT prove "everything after it is known"; it only proves *that one* is known. The reviewer will (correctly) block "zero loss" claims. Two design moves make it sound: (1) require a **run of K consecutive** already-known items before stopping (K≥3 makes an accidental skip require K known items to coincidentally precede a still-new one — implausible under stable ordering), and collect the WHOLE current page/batch before stopping so new items above the known run are kept; (2) add a **periodic full-pass safety net** (every N days/runs, skip the early-stop and traverse fully) that self-heals any below-frontier gap the daily early-stop structurally cannot see. State the honest loss posture in the Goal ("no loss above the *contiguous* known frontier; gaps are recovered by the safety net, not the daily run"), not "zero loss." Invariants: the terminal/optimization decision is gated on K-consecutive; the safety-net cadence resets only on a *completed* full pass (see prd-harden `references/post-build-diff-review-solo-builds.md` "incomplete-pass reset" trap). This whole pattern composes from the ground-truthed ordering guarantee (e.g. "the API paginates newest→oldest") — name that guarantee as the load-bearing assumption (D-6 style) and make the fail-open path over-fetch-within-bound, never drop, if it's ever violated.

- **When a fix could live in MULTIPLE layers (a proxy/relay/sidecar vs an edge helper vs the protected core), write a LAYER ANALYSIS before the design — ground-truth what each layer ALREADY does and what it CAN'T fix (2026-06-25).** The user's challenge "should we fix this in <the edge component> instead of core?" is the right instinct and usually reshapes the whole spec — but only if you answer it with measured per-layer facts, not reasoning. The recurring trap: a "missing X" symptom (no failover, no degrade, no retry) is often *already handled* by a layer you didn't read, and the real defect is a DIFFERENT layer multiplying/dropping the handled result. Real case: a "compaction summarizer has no fallback" spec was about to ADD a per-box fallback chain — until ground-truthing showed the relay ALREADY rotates across boxes internally AND the engine ALREADY has a guaranteed non-LLM degrade; the actual bug was the *client SDK* retrying a bounded relay 504 into a 30-min wedge. The fix collapsed from "build a chain" (big, multi-file) to "one route-scoped `max_retries=0` line + reuse the two existing mechanisms." **The discipline, as a spec section (§5A "Layer Analysis"):** (1) a table — `| layer | file | what it CAN fix | what it CANNOT fix | touches protected core? |` — with each row ground-truthed against the actual source, not assumed; (2) name the ONE thing that *must* live in the protected/core layer and the airtight reason it can't live elsewhere (here: "only the code that constructs the SDK client can stop the SDK's own retries — the relay is a different process and can't see client-side retries"); (3) confirm the core change is an *edge helper*, not the narrow waist the project guards (model-tool schema / prompt cache / agent loop) — and that it's also a general *correctness* fix (every aux task inherits the same wedge), which is what the rubric wants; (4) the "shrunk fix" then drops whatever the existing layers already cover. Two scope traps this surfaces that a reviewer WILL block on: a knob you lower on a SHARED component (a relay `request_deadline_s`, a factory-wide client setting) is a FLEET-WIDE/all-consumers contract change, not the scoped fix it looks like — make it per-route or treat the global change as its own measured decision; and reusing an existing degrade (e.g. a deterministic-truncation fallback) means accepting its QUALITY FLOOR explicitly (turn survives but lower quality), not letting "simpler" silently lower the bar. Same family as the discarded-intermediate trap (read the engine before declaring "needs new X"), applied to the build-vs-reuse + which-layer decision.

- **Before scoping a feature as "infeasible / needs a new dependency / new system," check whether a shared engine already COMPUTES the thing and just DISCARDS it (the discarded-intermediate trap, 2026-06-13).** The lazy feasibility verdict on a "show me X" ask is "X isn't available here — it'd need a new rate table / second pricing system / extra service." That verdict is wrong surprisingly often: the value already exists *inside* a shared engine that computes it as an intermediate and then throws it away, returning only an aggregate. Measured example: a dashboard ask for **per-class $ cost** was first scoped as "❌ not computable — this repo has no pricing engine, would need a per-model rate table = new dependency." The user pushed back ("we use OpenRouter prices in the plugin... can't we make those accessible? we shouldn't create two pricing systems"). Grounding the plugin proved him right: the ONE pricing engine (`agent.usage_pricing.estimate_usage_cost`) **already computes the four per-class $ terms line-by-line and then SUMS them**, returning only the total — the breakdown was discarded, not absent. The feature was "stop discarding it + persist it," not "build a second pricing system." **The reflex, three steps:** (1) when you're about to write "infeasible / needs new system" in a Non-Goal or feasibility table, FIRST read the source of whatever currently produces the *aggregate* version of that value — the per-item breakdown is frequently right there as a local that gets summed/reduced away; (2) treat the user's "we shouldn't have two X systems" as a *design directive that's almost always correct* — surfacing a discarded intermediate from the single source-of-truth engine beats minting a parallel one, and avoids the drift two systems guarantee; (3) write the feasibility verdict only AFTER reading the engine, and if it flips, say so plainly ("you're right — it's not a new system, it's a discarded intermediate"). The cheapest correctness win in a spec is deleting a phantom dependency you assumed before reading the code. (Same family as "ground-truth the live system BEFORE choosing the architecture," applied to the *build-vs-reuse / new-dependency* decision specifically.)

- **An Opus review that DEMANDS a live ground-truth probe can flip a "correct" fix into a SAFETY BUG —
  and the redesign it forces is usually SMALLER, not bigger (2026-06-30, brightness actuation).** A
  spec proposed firing `light.turn_on area_id=kitchen` (proven 200 + correct % scaling live). Pass-1
  Opus BLOCKed on a premise the spec ASSERTED but never measured: "does `area_id` bypass the floodlight
  sanitizer?" The cheap live probe (`light.turn_on area_id=kitchen` → inspect affected entities)
  returned `light.kitchen_floodlight` + `_floodlight_2` — the area_id fire expands server-side AFTER
  HACR's entity-id sanitizer runs, so every "dim the kitchen lights" would turn on the camera
  floodlights, and the unit test would be GREEN. Two durable lessons: (1) for any actuation that targets
  a GROUP/area/wildcard rather than enumerated entities, the load-bearing question is "does the
  server-side expansion happen BEFORE or AFTER my safety filter?" — answer it with a live
  affected-entity read, never assume; (2) the review's redesign collapsed a 5-file change (new
  `call_service` param + executor + validator + parser + superset) into a **~12-line fix in one
  already-safe function** — because the safe path (live-expand → sanitize → fire explicit list) ALREADY
  existed and the real bug was just a slot-units error (`brightness` raw-0-255 vs `brightness_pct`). When
  a review forces you back to "what does the codebase already do safely?", the answer is often a tiny
  edit to the existing safe seam, not new infrastructure. (Same family as the discarded-intermediate
  trap, applied to a safety boundary instead of a value.)
- **A bigger eval corpus can DISPROVE the spec's root-cause hypothesis — that's the eval working, not
  failing; pivot the fix track (2026-06-30, STT onset).** An STT-accuracy spec was built on "fix
  'dim'→'Jim' via word-boost." The honest normalized-WER eval on a 13→70-sample corpus showed 9 of 12
  "dim" phrasings transcribe PERFECTLY, and the genuine errors were word-INITIAL across DIFFERENT words
  ("dim→Dam", "set→Sat", "mute→''") — i.e. the model gets garbled ONSET audio, not a word-confusion, so
  **word-boost (the spec's whole Rec 1) cannot fix it** and the real lever is the acoustic/onset track.
  The lesson for a spec whose load-bearing premise is "error X is caused by Y": treat the small initial
  sample as an ANECDOTE (the pass-1 review will correctly flag n=13 as a non-gate), and make
  "grow the corpus / re-measure before committing to the fix mechanism" a hard precondition — because the
  bigger sample routinely re-classifies the error and re-points the fix. Don't ship the tuning built on
  the small-n hypothesis.

## Minimal output when time is tight

If the user wants a quick spec, still include:

- Goal / non-goals
- Decisions
- Phases with Verification blocks
- Acceptance criteria
- Risks / rollback

Cut prose, not verification.

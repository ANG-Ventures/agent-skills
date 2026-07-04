# PRD suite — ownership map

The **single index of who-owns-what** across the `prd-*` skill suite (the fleet's PRD lifecycle:
interview → spec → review → plan/swarm-plan → build → harden → closeout, with `prd-document` and
`prd-share` as cross-cutting helpers). It exists so an editor improving one skill can tell, at a glance,
whether a passage is **canonical-here** (edit it) or **duplicated-from-there** (fix the owner, leave a
pointer). Drift between two copies of a rule means an agent follows the stale one confidently — this map
is the cure.

This doc is **hand-authored** (not generated): the skills carry no machine-readable `canonical-owner`
marker, so a generator would be a sub-project larger than the suite it indexes. Because it's hand-kept,
**INV-3 (one-home-per-concept) is a convention here, not a guarded invariant** — the guard
(`prd-closeout/scripts/prd-suite-pointer-guard.py`, loaded via
`skill_view(name='prd-closeout', file_path='scripts/prd-suite-pointer-guard.py')`) enforces that pointers
*resolve*, not that ownership is unique. Keep this table honest by hand: when you move a concept's home,
update the row.

> **For the lifecycle graph itself (phases + order), do NOT look here** — it lives in
> `skill_view(name='prd-spec', file_path='references/lifecycle.md')`, the single canonical diagram.
> This map indexes *concept ownership*; that file owns the *flow*.

## The map

| Concept | Canonical owner | Pointed to from |
|---|---|---|
| Lifecycle graph (phases + order) | `prd-spec/references/lifecycle.md` | all prd-* (one-line neighbor inline + pointer) |
| The PRD/spec document + per-phase Verification blocks | `prd-spec` | plan, harden, closeout |
| Constitution / Invariants format (the 3 buckets) | `prd-spec` → "Constitution / Invariants" | closeout, review |
| Interview a vague idea → concrete scoped brief | `prd-interview` (entry skill) | spec |
| Minimal-diff / minimum-viable-change | `coding-guardrails` (external to suite) | spec |
| Bite-sized TDD task breakdown (serial) | `prd-plan` | spec |
| Parallel task-DAG / swarm decomposition | `prd-swarm-plan` | plan, swarm-plan-review |
| Swarm-plan lint-before-dispatch | `prd-swarm-plan-review` | swarm-plan |
| Senior adversarial review + **Opus fallback order** | `prd-review-pipeline` | spec, closeout |
| Hardening (e2e / negative / concurrency / idempotency gates) | `prd-harden` | closeout |
| Bounded architecture-preserving refactor (blast-radius map, frozen contracts, concrete stop condition) | `prd-refactor` | simplify-code, coding-guardrails |
| Doc mechanics + Obsidian Portability Rule + **mem0 fact-hygiene** | `prd-document` | closeout |
| **Doc freshness stamping (`canonical_as_of`/`review_every_days`) + the freshness sweeper** | `prd-document` → step 3 + `scripts/doc-freshness-sweep.py` | closeout (runs the sweep as a docs gate) |
| **Trust-tier ladder for resolving doc conflicts** | `prd-document` → "Trust tiers & freshness" | closeout |
| **Self-learning: draft→final delta folded back into the skill** | `prd-closeout` → "Self-learning" | — |
| **Dual-format delivery rule** | `prd-share` → "The delivery rule (canonical)" | spec, document, closeout |
| **Elaborate Open Questions inline in chat (not only in the doc)** | `prd-share` → "The delivery rule (canonical)" point 3 | spec, review-pipeline, closeout |
| Exit gate + request DONE-marker + loose-end triage | `prd-closeout` | — |
| Git push-proof discipline (`cat-file -e` proves existence, not content) | `prd-closeout` (single-home on disk) | — |
| "Ground against disk — a checkbox/summary is a claim, not a fact" | `prd-closeout` (primary); applied in-domain by spec, review, plan, harden, document | — |
| "Skills are docs too — update the skill that teaches the changed subsystem" | `prd-closeout` (single-home on disk) | — |

> **Why no shared `prd-suite-doctrine.md`?** The DRY spec (2026-06-21) considered lifting the
> git-push-proof + ground-against-disk + skills-are-docs rules into a new shared doctrine file (Q2/Option A).
> The Phase-0 disk audit found they are **already single-homed in `prd-closeout`** (push-proof: 8 hits all in
> closeout; skills-are-docs: 5 hits all in closeout; ground-against-disk: a small shared *statement* plus
> domain-specific applications that are correctly local). Lifting them would create indirection without
> removing duplication. They stay in `prd-closeout`; this map records that as their home.

## Tombstones (redirects, not concepts)

- `writing-plans` → **RENAMED → load `prd-plan`**. Kept as a redirect (has live inbound refs); its
  `→ prd-plan` pointer is integrity-checked by the guard.
- *(`prd-swarm-planner` was retired 2026-06-21 — its inbound refs were repointed to `prd-swarm-plan`.)*

## How to use this map when editing

1. Find the concept you're about to write about.
2. If you're **not** in its canonical owner, do **not** restate it — replace your prose with a one-line
   pointer (`skill_view(name='<owner>', file_path='SKILL.md')` + the section, if relevant) and stop.
3. If you **are** the owner, edit freely — yours is the copy that matters.
4. If the concept isn't in the table, it's either local-and-single-use (fine, keep it inline) or a new
   shared concept (add a row naming its one home).

The guard (`prd-closeout/scripts/prd-suite-pointer-guard.py` — closeout runs it in its exit gate; also
wired pre-commit) only checks that pointers *resolve*. Keeping ownership *unique* is on you and this table.

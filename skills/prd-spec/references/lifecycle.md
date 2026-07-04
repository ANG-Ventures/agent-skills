# The PRD lifecycle (canonical diagram)

This is the **single canonical "position in the lifecycle" diagram** for the prd-* skill suite. Every prd-* skill points here (via `skill_view(name='prd-spec', file_path='references/lifecycle.md')`) plus states its own immediate upstream/downstream neighbor inline — only the full diagram is centralized.

> **This diagram is a NORMALIZED SUPERSET, not a verbatim copy of any one skill's old diagram.** The 5 skills that used to each draw their own "Position in the lifecycle" block had **divergent** diagrams (some omitted `interview`, some omitted `harden`, the swarm skill had its own sub-loop). The canonical diagram below is the deliberate union of all stages. See the reconciliation note in `prd-spec/references/lifecycle-reconciliation.md`.

## The full lifecycle

```text
prd-interview → prd-spec → prd-review-pipeline → prd-swarm-plan(plan)
                                                      ↓
                                              prd-swarm-plan-review
                                                      ↓
                              prd-swarm-plan(load → run) / prd-plan
                                                      ↓
                                                    build
                                                      ↓
                                                 prd-harden
                                                      ↓
                                                 prd-closeout

cross-cutting (not a linear stage): prd-document (keep docs current, any time)
                                    handoff-doc   (compact a session, any time)
```

## One-line role of each stage

- **prd-interview** — turn a vague idea into a concrete, scoped brief before any spec is written. *Upstream:* (the raw idea). *Downstream:* prd-spec.
- **prd-spec** — author the PRD/spec (Constitution/Invariants, per-phase Verification blocks, delivery via `prd-share`). *Upstream:* prd-interview. *Downstream:* prd-review-pipeline.
- **prd-review-pipeline** — senior adversarial review (Opus-only) of the spec before any build; review→fix passes until APPROVE. *Upstream:* prd-spec. *Downstream:* prd-swarm-plan / prd-plan.
- **prd-swarm-plan (plan)** — decompose an approved PRD into a dependency-aware swarm of bite-sized worker tasks. *Upstream:* prd-review-pipeline. *Downstream:* prd-swarm-plan-review.
- **prd-swarm-plan-review** — lint the swarm plan for dispatch viability before launching workers. *Upstream:* prd-swarm-plan(plan). *Downstream:* prd-swarm-plan(load → run).
- **prd-swarm-plan (load → run) / prd-plan** — dispatch the workers (swarm) or write the bite-sized TDD task list (solo). *Downstream:* build.
- **build** — implement the feature and pass its first tests.
- **prd-harden** — the deliberate hardening pass between a green build and closeout: drive e2e + lint gates + negative/adversarial/concurrency/idempotency coverage of the real failure paths. Stamps the commit SHA it ran against (so closeout can check freshness). *Upstream:* build. *Downstream:* prd-closeout.
- **prd-closeout** — the single orchestrating exit gate. It **calls `prd-harden`** (run it, or confirm a *current* hardening report whose recorded state matches the build) **and calls `prd-document`** (project docs + Obsidian current), then runs its own gate (GitHub push + thorough changelog + memory/mem0 + cron/alerts + loose ends). BLOCKs if harden surfaces unclosed failure paths or the report is stale. *Upstream:* prd-harden.
- **prd-document** *(cross-cutting)* — bring docs back into agreement with reality; owns the canonical documentation procedure + Obsidian Portability Rule. Invoked by prd-closeout, or used standalone for a docs-only refresh.
- **handoff-doc** *(cross-cutting, lives under `skills-shared/coding/`)* — compact the current session into a portable handoff document. Not a prd-* skill; referenced here only because it composes with the lifecycle.

## The convention

Each prd-* skill states its **immediate upstream and downstream neighbor** inline (a one-liner), and points here for the full picture. Keep the local neighbor pointers in each skill — they're skill-specific and the self-correcting "did I fire at the right stage?" behavior depends on them. Only this full diagram is single-sourced.

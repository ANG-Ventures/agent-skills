# Reconciliation note — lifecycle diagram + dual-format rule consolidation (v14)

This records the deliberate deltas when the cross-cutting rules were single-sourced (PRD v14, 2026-06-11). Per D10, where a consolidated rule is a *normalization* rather than a verbatim relocation, the delta is recorded here and called out as an approved §2 exception — not smuggled under "verbatim."

## 1. Lifecycle diagram — NORMALIZED SUPERSET (approved §2 exception)

The 5 skills that each drew their own "Position in the lifecycle" block had **divergent** diagrams (verified 2026-06-10/11):

| Skill | Its old diagram | What it was missing vs the superset |
|---|---|---|
| `prd-interview` | `prd-interview → prd-spec → prd-review-pipeline → prd-swarm-plan / prd-plan → build → prd-closeout` | no `prd-harden`; no swarm-plan-review sub-loop |
| `prd-spec` | `prd-spec → prd-review-pipeline → prd-swarm-plan / prd-plan → build → prd-closeout` | no `prd-interview`; no `prd-harden`; no swarm-plan-review |
| `prd-closeout` | `prd-spec → prd-review-pipeline → prd-swarm-plan / prd-plan → build → prd-harden → prd-closeout` | no `prd-interview`; no swarm-plan-review |
| `prd-harden` | `prd-spec → prd-review-pipeline → swarm/plan → build → prd-harden → prd-closeout` | no `prd-interview`; swarm stages collapsed to "swarm/plan" |
| `prd-swarm-plan-review` | `prd-spec → prd-review-pipeline → prd-swarm-plan(plan) → prd-swarm-plan-review → prd-swarm-plan(load → run) → prd-closeout` | no `prd-interview`; no `prd-harden` |

**Canonical composed superset** (in `lifecycle.md`): `prd-interview → prd-spec → prd-review-pipeline → prd-swarm-plan(plan) → prd-swarm-plan-review → prd-swarm-plan(load → run)/prd-plan → build → prd-harden → prd-closeout`, with `prd-document` + `handoff-doc` as cross-cutting.

This is the **union of all 5 variants** — no stage any variant had was dropped; stages some variants lacked were added. The closeout stage's role line is written **D9-aware** from the start ("closeout *calls* harden + document, then runs its own gate") so the canonical diagram does not ship stale relative to the Phase-5 closeout edit.

## 2. Dual-format delivery rule — drifted copies, reconciled to prd-share

The 3 copies (prd-spec §"Delivery & doc shapes", prd-document §"Dual-format rule", prd-closeout relationship note) said the **same rule** but with **drifted wording** (prd-spec's was the fullest with the numbered project-docs/Obsidian breakdown; prd-document's was a tighter 2-bullet form). Canonical text in `prd-share` → "The delivery rule (canonical)" uses the **fullest wording** (prd-spec's numbered form) so no nuance is lost. The §10.1 row-1 discriminating string **"every saved file gets Markdown"** is present in the canonical prd-share copy.

- `prd-document` keeps ONLY its doc-specific nuance (vault note = `.md`, why Obsidian can't render HTML) inside its documentation procedure — that's not the general delivery rule, it's the Obsidian-Portability detail prd-document legitimately owns.
- This is a **verbatim-meaning relocation** (the rule's meaning is unchanged), with a wording pick recorded here — it is the lighter case, not a semantic normalization like the lifecycle diagram. No new §2 exception needed beyond noting the wording choice.

## 3. The §2 intentional exceptions (recap)

1. **D9** — prd-closeout's behavior changes (it now *calls* prd-harden instead of bouncing to it).
2. **D4/D10** — the lifecycle diagram is a normalized superset (this note §1).
3. **D11** — prd-harden's report format gains one line (`Ran against: <SHA>`); its procedure is untouched.

Everything else is verbatim text relocation replaced by one-sentence `skill_view` pointers.

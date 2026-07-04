---
name: verifying-beyond-green-tests
description: >
  Prove a code change is ACTUALLY correct, not just unit-green. Load whenever a build/fix comes
  back with a passing unit suite but touches a persisted field, a resume/recovery path, cross-process
  or restart-surviving state, a plugin's live wiring, auth/identity, or data eviction — i.e. anything
  where "each part works in isolation" is NOT the same as "the assembled, round-tripped, persisted
  thing is correct." Its whole job is to name the seams a green in-memory unit suite is structurally
  BLIND to, and the cheap tests that expose them. Triggers: "all tests pass but", "N/N green",
  "does this actually work in prod", "will this survive a restart / reload", "new field on a stored
  record", "the feature no-ops", "unit-green vs integration", "round-trip test", "persistence key drop".
  Companion to the (read-only) coding-guardrails + subagent-driven-development "unit-green is not an
  integration pass" sections; this is the editable, class-level home for the verification discipline.
version: 1.0.0
---

# Verifying Beyond Green Tests

A green unit suite proves "each part works as written." It does NOT prove the **assembled, round-tripped,
persisted, wired** thing is correct. The most expensive fleet bugs ship WITH a fully-green unit suite,
because the tests exercised code in isolation and never touched the real seam that breaks. This skill is
the checklist for the seams a green in-memory suite is structurally blind to.

## The one-line tell
**If a test would pass IDENTICALLY whether the persistence / registration / cross-process / restart wiring
existed or not, it is not testing the thing that ships.** Add the test that goes RED when the real seam is
broken. Everything below is a specialization of this.

## Seam 1 — Persistence-layer key/field drop (the silent no-op)
**Symptom:** you add a field to a record (a discriminator flag, metadata key, extra attribute) by setting
an arbitrary key on an in-memory dict/object; later code reads it back; all unit tests green; the feature
does nothing in production.

**Why:** the persistence layer serializes by KNOWN fields — a fixed-column SQLite table, a Pydantic model
with declared fields, a protobuf, a `to_dict()` that enumerates keys, a JSON schema with
`additionalProperties:false`. An arbitrary key has no home → **dropped on write, never returned on read.**
If the consumer reads the RELOADED value (not the in-memory one), the discriminator is always False in
prod. In-memory unit tests never see it (an extra dict key trivially survives in memory).

**Verified case (2026-06-30, preserve-and-prompt gateway restart):** `msg["_interrupt_close"]=True` set on
a synthetic turn; resume site keyed on it but read from the reloaded history
(`session_db.get_messages()`). `hermes_state.append_message` takes only named column params; `get_messages`
rebuilds from columns. The key had no column → dropped → surface-and-ask branch never fired → the whole
fix was a silent no-op. 12 in-memory unit tests were green; only the HEAVY diff-review + a schema grep
caught it.

**Do:**
- Before adding an arbitrary key to a persisted record, **grep the store's writer + schema**:
  `grep -nE 'def append_message|def save|def to_dict|CREATE TABLE|class .*\(BaseModel\)|additionalProperties'`.
  Assume drop-by-default for any typed/columnar/serialized store until proven otherwise.
- **Real round-trip acceptance test:** write via the actual store API to a temp home, reload via the actual
  read API, assert the field survived. An in-memory round-trip proves nothing.
- **Fix by reusing an EXISTING round-tripping field, not a schema migration.** (Case above: moved the flag
  onto `finish_reason="interrupt_close"`, an existing column `get_messages` already restores, collision-
  proof, zero migration.) Extend-don't-duplicate applied to persistence.

## Seam 2 — Cross-process / restart-surviving state
Per-process ephemeral state (an in-memory dict, a per-boot cache, a `_session_initiated_restart` flag)
is GONE after a restart/SIGKILL. If a "durable" guarantee reads it after the process died, it fails open.
Verified pattern (gateway self-restart-loop gate): the durable signal must be an on-disk artifact written
BEFORE the process can die (a breadcrumb file / a committed DB row), not an in-memory flag. Test by driving
a REAL restart (or a persist→hard-kill→reload fixture), not by forcing the in-memory flag in a unit test —
the flag is exactly what's lost.

## Seam 3 — Live wiring / registration
A `register()` that wires hooks but never registers the actual tool the emitted marker tells the model to
call = silent permanent failure. A unit test of the hook passes; the tool is never callable. Test the
real `register()` against the real loader and assert the tool is invocable end-to-end.

## Seam 4 — Turn/round scoping on a one-shot gate
A per-turn interlock that consumes its flag on the FIRST invocation leaks on round 2 of the SAME agentic
turn (block-results feed back to the model, which re-emits calls with the gate already cleared). Verified
2026-06-30: the INV-D7 resume interlock cleared on first block → round-2 tool executed; the test enshrined
the hole by asserting the second call runs. Scope the gate to the correct boundary (the whole turn, until
the next genuine human message), and write the two-rounds-same-turn RED test.

## The gate, operationally
On any high-blast-radius change — lossless/durable, auth/identity, data-eviction, cross-process/restart
state, plugin live-wiring, a NEW persisted field, a resume/recovery path — do NOT accept N/N green as
shippable. Run the senior diff-review, **put the test files in the review pack** (a reviewer can't certify
gates it can't see), and for each blocker verify against the real code (`grep`/`sed` the cited line) before
fixing — a blocker is a claim too, occasionally stale. Converge per the review pipeline's "no NEW blocker"
rule.

## Cross-refs
- `coding-guardrails` (read-only) — the canonical "done right" reference; §"unit-green is not an integration
  pass".
- `subagent-driven-development` (read-only) — §"A clean UNIT-suite green is NOT an integration-review pass".
- `systematic-debugging` / `prd-review-pipeline` — the instrument-before-theorize + review-convergence loops.

---
name: prd-interview
description: "Interview the user to turn a vague idea into a concrete, specable problem before writing a PRD. Use when the user says 'grill me', 'interview me', 'ask hard questions', 'pressure-test this plan/design', 'help me figure out what I actually want', 'clarify scope/requirements', or when a request headed for prd-spec is too vague to spec. Research-first (never ask what you can read), asks only judgment calls, batches 2-3 questions per turn, recommends an answer for each, can optionally sketch 2-3 rough design directions as light-mode ideation before locking the PRD, forces concreteness on vague answers, and stops before implementation with a one-line problem statement + measurable success criteria. Feeds prd-spec."
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, prd, interview, requirements, scoping]
    related_skills: [prd-spec, prd-review-pipeline, prd-swarm-plan, prd-plan]
---

# PRD Interview

Use this skill to converge a fuzzy request ("I want X to be better / easier / smarter") into a problem statement and success criteria concrete enough that `prd-spec` can write a real spec. The job is to *extract and sharpen intent*, not to design or build.

The whole value is discipline: research before asking, ask only what genuinely needs the human's judgment, recommend an answer every time so the user can react instead of inventing, and refuse to let vague answers stand. Done right, this prevents the two failure modes that wreck specs — **under-asking** (you guess wrong and build the wrong thing) and **over-asking** (you interrogate the user about facts you could have read, and they stop trusting you).

## Position in the lifecycle

This skill's place in the full lifecycle: see `skill_view(name='prd-spec', file_path='references/lifecycle.md')`. For **who owns which concept** in this suite, see the ownership map: `skill_view(name='prd-spec', file_path='references/prd-suite-map.md')`. **Immediately upstream:** (the raw idea). **Immediately downstream:** `prd-spec`.

When the interview converges, hand the Snapshot to `prd-spec`: "now author the PRD from this Snapshot." Name that next step explicitly when you finish.

## The one rule above all others: research first

**Never ask the user for a fact you can discover yourself.** Before every question, ask: "could I answer this by reading the repo, the files, the config, the existing docs, or the conversation?" If yes — go find it, record it as a Fact, and move on. Asking discoverable facts ("what language is this in?", "do you have a test runner?") is the fastest way to annoy the user and signal you're not paying attention.

Spend real effort here. Read the relevant code, configs, existing PRDs/docs, and prior session context. The more you discover, the fewer (and sharper) your questions.

### Research-first applies to DECISIONS, not just facts — check for an already-locked decision before asking

The most expensive over-ask is re-interviewing the user on something **already decided in a prior session**. Before you ask a judgment call, grep the project for an existing decisions record — a `prd-*.md` "Resolved Decisions" table, a `DECISIONS-*.md` ledger, an the AGENTS doc "locked decisions" pointer, or the parent PRD's invariant/decision section. If the question maps to a locked row, **cite the row and move on — do NOT re-ask it**, even slightly reworded. The tell that you're about to make this mistake: you're treating a long-lived project as greenfield because a compaction/handoff banner made it *read* fresh (same trap as prd-spec's "ground-truth the live file before editing"). When the user pushes back with *"didn't we already spec this?"*, that IS a correction — stop, go read the existing spec, and show LOCKED-vs-OPEN instead of restating questions. (Proven 2026-06-16, the voice assistant routing: nearly re-interviewed persona/latency/routing that were already D-1…D-16 in a 123KB PRD; the user had to ask twice.)

**The ledger can ITSELF be stale — never trust its "Genuinely OPEN" section as authoritative without checking sibling PRDs on disk.** A decisions ledger is only as fresh as the last time someone updated it; its OPEN section routinely lags the actual specs, because a PRD gets written + APPROVED to resolve an open row but nobody goes back and moves the row out of OPEN. So before you interview on *anything the ledger lists as open*, do the second check: **`ls`/grep the project `docs/` dir for sibling `prd-*.md` files whose title or §1 maps to that row, and read their Status line.** If you find a `Status: ✅ APPROVED` (or worse, an `Approved + BUILT` with a `PHASE-N-result.md` next to it) covering the "open" question, the row is *resolved, not open* — the ledger is wrong, not the PRD. Then: (a) run the interview only on rows that survive BOTH checks; (b) **fix the stale ledger** (move the row OPEN→LOCKED, point it at the approved PRD as its source, add a build-status table) rather than minting fresh decision IDs as if you'd just decided them; (c) the real next step is almost certainly *building the next unbuilt phase of the existing approved PRD*, NOT authoring a new PRD. (Proven 2026-06-16, the voice assistant routing-v1/phase-2: the ledger's OPEN listed O-1/O-2/O-3; I ground-truthed the ledger but not `docs/`, ran a full interview, and minted D-17/18/19 — only to find both decisions were already APPROVED PRDs and Phase 2 was already built this same session. Correct move was: patch the ledger to cite the approved PRDs + start the Phase-3 build.) **Mechanical rule: ground-truth = ledger AND the `docs/` PRD set, never the ledger alone.**

### When decisions are scattered across a big PRD, BUILD a locked-decisions ledger (the "so we don't lose track" pattern)

When a project's decisions live spread across a large parent PRD + sibling specs (so each session keeps re-litigating them), the durable fix the user wants — and will ask for explicitly (*"document this better so we don't lose track"*) — is a **single-source decisions ledger**, not another paragraph buried in the PRD:

- A `DECISIONS-<project>-locked.md` with **LOCKED tables** (one row per decision: topic · value · pointer to the authoritative spec) and a small **"Genuinely OPEN"** section that is the *only* fair game for a new interview.
- A **one-line pointer at the top of the AGENTS doc** ("read this before re-deciding ANYTHING") so a fresh-context session finds it without loading the whole PRD.
- A **"Known drift"** section when the live system has diverged from the locked design (live-vs-spec gaps are not open questions; they're realignment work).
- Reaffirm any decision the user re-confirms this session **in both the ledger and the authoritative spec, same commit**, dated — so the two never disagree.

This converts "we keep losing track across a 123KB PRD" into a one-screen index. It is itself an interview output: write it when the symptom appears, before running the (now-narrow) interview on the OPEN rows only.

## Maintain a running Snapshot

Keep a visible, updated Snapshot throughout the interview. It is the working state and becomes the handoff artifact:

```markdown
## Snapshot
**Facts** (discovered, not asked):
- …
**Decisions** (made this interview):
- …
**Open Questions** (ordered queue):
1. …
```

Update it every turn. When Open Questions is empty (or the user exits), the Snapshot *is* the output.

## Ask only judgment calls

A judgment call is a question whose answer depends on what the *user wants*, not on what is true about the system — objectives, priorities, trade-offs, scope boundaries, acceptable costs, definitions of "good enough." Those are the only things worth a human's turn.

How to ask:

- **Batch 2–3 independent questions per turn.** Use a single question only when the next question genuinely depends on this answer (a sequenced branch). Don't drip one question per turn when three are independent — that wastes the user's time as surely as over-asking.
- **Recommend an answer for every question — as a lite 1-3-1.** This is the signature move: don't just interrogate, advise. Frame each judgment call as Problem → 2-3 genuine Options (trade-off + counter-case each) → Recommendation with a one-line why: "I'd default to X because Y — agree, or do you want Z?" The user can react to a concrete proposal far faster than they can generate one from scratch, and your recommendation surfaces your reasoning for them to correct. (Format is canonical in `prd-share` → "The delivery rule (canonical)" point 3; the design-sketch calls use the full 1-3-1 with DoD + plan.)
- **Walk the decision tree in order:** resolve a parent decision before its dependents. Don't ask about an edge case whose existence depends on an unresolved earlier choice.

**Priority order for the queue:** objective (what problem, for whom, why now) → constraints (budget, hosting, deadlines, must-use/must-avoid) → non-goals (what explicitly won't ship) → trade-offs (speed vs completeness, cost vs quality) → acceptance signal (how we'll know it worked).

If the objective is still too vague to choose scope after research and the first judgment-call pass, insert **OPTIONAL design-sketch light-mode** before locking the Snapshot. Then return to the same queue: pick/merge/park a direction, force measurable success criteria, and hand off to `prd-spec`.

## OPTIONAL mode: design-sketch light-mode

Use this only when the user has a fuzzy product/design intent but cannot yet choose the shape of the PRD. It is the lightweight brainstorm path for `prd-interview`; do **not** create or invoke a standalone brainstorm skill.


How to run it:

1. **Sketch 2–3 rough directions, not an implementation.** Each direction gets a short name, who it serves, the user-visible behavior, one likely trade-off, and the success signal it would optimize.
2. **Recommend a default direction.** Say which sketch you would lock for the PRD and why, so the user can accept, combine, or reject from something concrete.
3. **Record the outcome in the Snapshot.** Add the selected direction under Decisions and list parked/rejected directions as Non-goals or Open Questions. If no direction is chosen by the round cap, carry the sketches forward as gaps for `prd-spec`.
4. **Stop before architecture.** No schemas, file paths, stack choices, implementation phases, or detailed UX flows. This mode clarifies product intent; it does not design the system.

Template:

```markdown
## Optional design-sketch light-mode

1. **[Direction A]** — [user-visible shape]; optimizes [success signal]; trade-off: [cost/risk].
2. **[Direction B]** — [user-visible shape]; optimizes [success signal]; trade-off: [cost/risk].
3. **[Direction C]** — [optional third shape]; optimizes [success signal]; trade-off: [cost/risk].

**Recommended lock:** [direction] because [reason]. Agree, combine, or reject?
```

## Force concreteness

If an answer is vague — "faster", "soon", "better", "more reliable", "a lot" — **re-ask the same question** (keep the same Open-Question id) and demand a metric, a date, a scope boundary, or a named behavior:

- "faster" → "faster than what, measured how? e.g. p95 < 200ms vs today's 1.2s"
- "soon" → "by what date, or before what event?"
- "better search" → "better at *which* of: known-item recall, rediscovery, or browsing? give me the one query that's failing today"

A spec built on adjectives is a spec that can't be tested. The downstream `prd-spec` skill bans subjective adjectives in requirements — catch them here, at the source, where the human can clarify.

## Stop before implementation

This skill does **not** design the system or write the PRD. Exit the moment the Snapshot has:

1. a **one-line problem statement** (who, what, why now),
2. **measurable success criteria** (at least one threshold/metric/date/named-behavior), and
3. **no blocking open questions**.

Then emit a clarification summary and hand to `prd-spec`. If you catch yourself proposing architecture, sketching schemas, or naming files — stop; that's the next skill's job.

## Termination guarantees — never grill forever

An interview that won't end is worse than one that ends slightly early. Two hard exits:

- **User early-exit always wins.** "good enough, draft it" / "stop, that's enough" / "just write it" immediately ends the interview and emits the Snapshot as-is (with remaining Open Questions flagged as gaps for `prd-spec` to record).
- **Round cap (~5 question-batches).** After roughly five batches, stop on your own, emit the Snapshot, flag any unresolved questions explicitly as gaps, and hand to `prd-spec`. **Force-concreteness re-asks count toward the cap** — a user who keeps answering vaguely can't trap the loop forever; record the residual fuzz as an Open Question and move on.

## Output (the clarification summary)

When you stop, emit:

```markdown
## Interview complete — handoff to prd-spec

**Problem statement:** [one line — who/what/why now]

**Success criteria (measurable):**
- [threshold / metric / date / named behavior]

**Key decisions:**
- [decision → value]

**Non-goals:**
- [what won't ship]

**Open questions / gaps** (for the PRD to record):
- [unresolved — or "None"]

→ Next: run `prd-spec` to write the PRD from this Snapshot.
```

## Mechanics

Use the native question/clarify tool when one is available (it renders choices cleanly). Otherwise present a compact numbered block — question, your recommended answer, and the alternatives — so the user can reply "1: yes, 2: your call, 3: actually Z."

## Common pitfalls

- **Asking discoverable facts.** The cardinal sin. Read first.
- **One question at a time when three are independent.** Batch them.
- **Interrogating without advising.** Always recommend an answer.
- **Letting "better/faster/soon" stand.** Re-ask for a number, date, or boundary.
- **Sliding into design.** You're scoping the problem, not solving it. Stop at success criteria.
- **Never terminating.** Honor the early-exit and the round cap.
- **Answers arrive for questions you can no longer quote (the post-compaction batched-Q&A trap).** A
  batched interview ("Q1 / Q2 / Q3, here's my recommendation for each") spans turns, and the verbatim
  question text can fall into a compacted/handoff window — so the user's reply ("Q1) A>B>C; Q2) both;
  Q3) full history") lands while you no longer have the exact questions in front of you. Do NOT fabricate
  three plausible-looking questions and pretend they're what you asked — that silently mis-records intent,
  and an ambiguous shorthand answer ("both" — both of *which* two options?) can map to the wrong thing.
  The honest, reusable move: (1) say plainly you can't quote the originals (compaction); (2) **reconstruct
  the most-likely questions from the now-well-defined domain** and the answer shapes, mapping each answer
  onto your reconstruction, **explicitly labeled as reconstruction**; (3) flag any genuinely ambiguous
  answer as the one thing you need confirmed (the "both" = which pair?); (4) lock the Snapshot only after
  the user confirms/corrects. Try `session_search`/memory recall first — but when both come up empty,
  reconstruct-and-confirm beats either fabricating or making the user re-type everything. (Proven
  2026-06-14: Purchase-Tracker Q1/Q2/Q3 answers arrived post-compaction; reconstructing + flagging the
  "both" ambiguity surfaced it as option (iii) cleanly, and the user then pasted the real questions which
  matched the reconstruction.)

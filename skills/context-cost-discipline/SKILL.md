---
name: context-cost-discipline
description: "Operating doctrine for spending tokens, dollars, and context budget well — before and during any non-trivial task. Use when deciding whether a task is worth heavy fan-out, how many subagents to spawn, which model tier goes where, whether you're about to spend heavily on context, or the cost-aware way to do X. Triggers: \"is this worth the spend\", \"how many workers\", \"am I about to run out of context\", \"which model for this\", \"this is getting expensive\", \"right-size this task\", or any time you fan out subagents, start a long run, or pick a model for bulk work. OPERATING discipline (how to spend); to MEASURE what you spent, see blackbox-turn-telemetry."
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [cost, tokens, context, budget, model-routing, fan-out, delegation, efficiency, 200k]
    category: general
    related_skills: [blackbox-turn-telemetry, deep-research, structured-handoff, handoff-doc]
---

# Context & Cost Discipline

The decision framework for spending the three budgets every task draws down — **tokens**
(the primary lever and primary cost), **dollars** (model billing), and **context window**
(the 200k hard ceiling) — well. It is *operating* discipline: what to decide before you
start and what to watch while you run. It is **not** observability — to *measure* what a
turn actually cost, use `blackbox-turn-telemetry` (`/cost`); this skill tells you how to
*spend* so the measurement comes back small.

> **One-line rule:** *Being right AND cheap AND readable is the goal — in that order, but
> never dropping the second two.* A correct answer that cost 10× what it needed is a
> half-win; a complete-looking report nobody finishes is a loss.

## When to reach for this
- You're about to **fan out subagents** and aren't sure how many.
- You're about to **start a long multi-step run** (research, refactor, swarm).
- You need to **pick a model** for bulk vs. judgment work.
- You're **mid-run and the context bar is climbing** toward the ceiling.
- Someone asks "**is this worth it / right-size this / why is this so expensive.**"

When NOT to: a single cheap lookup or a one-shot edit. Don't pre-flight a `grep`.

---

## The levers, ranked (spend attention here, in this order)

### 1. Model routing — strong lead, cheap bulk *(the biggest single lever)*
Bulk gathering / low-judgment work is **high-volume, low-stakes** → route it to the cheap
model (`gpt-5.5` / `openai-codex`). **Reserve the expensive model (Opus/Sonnet) for the
three roles that carry judgment: the lead, the one-shot synthesis, and the
citation/verification pass.** Never let bulk workers silently inherit the lead's premium
model — that's the most common 10× overspend.
- Set a profile's `delegation.model` to `gpt-5.5`/`openai-codex` so native `delegate_task`
  children inherit cheap; the scripted lane path (`delegate.py`) already pins
  `--harness codex-acp --model gpt-5.5`.
- **Crons/background jobs:** cheapest predictable model that does the job (e.g. `gpt-5.x-mini`)
  unless the task genuinely needs reasoning.
- **Eval / test-loop / benchmark model = the CHEAPEST model that gives a clean baseline, NOT
  the smartest.** An eval measures a *delta* (does compression/retrieval/a change PRESERVE the
  load-bearing fact vs. an uncompressed control?), so you only need a model strong enough that
  the **baseline scores ≈ perfect** — then any failure is attributable to the thing under test,
  not the model's reasoning. Pay Opus/Sonnet rates per-trial across hundreds of replicates and
  you've burned money for zero signal gain. Validate empirically (baseline must actually hit
  ~1.0 — if it doesn't, the corpus/oracle is unfair, fix that, don't reach for a smarter model),
  then pin the cheap model for every run. Bonus: a cheap model (e.g. Haiku) often **dodges the
  burst-429 contention** that Opus/Sonnet hit on a shared local proxy serving live gateways.
  (Proven: PRD-6 compression eval D-7 — Haiku `claude-haiku-4-5` scored 23/23 baseline, pinned
  via `EVAL_MODEL`; Opus/Sonnet persistently 429'd real-size payloads on the Linux GPU box's shared proxy.)
- **The check:** before fan-out, ask "is any worker about to run on Opus by default?" If
  yes and it's gathering, fix it.
- **"Run it LOCAL to save cost" is usually a NON-REASON for an infrequent/scheduled/batched job — do the
  arithmetic before spec'ing local.** A cheap cloud model (gemini-flash / Haiku) at a *weekly* or *daily
  batched* cadence costs **cents per month**, not dollars — so "local for cost" cargo-cults a rationale
  that only applies to *per-turn / continuous* inference (which is exactly why a thing like Honcho needs a
  trained small model — it reasons on every turn). Worked: a weekly reflection job over ~40K-in/10K-out is
  ~$0.02/run on gemini-flash = **~$0.08/month**; even Sonnet is ~$1.20/month. At that cadence the *real*
  viability lever is the **schedule (batch it), not the host.** And local is usually the *worse* pick on
  the axes that matter: cloud is simpler (no serving rig to keep alive), higher quality (helps a precision
  gate), and consistent with a stack that already crosses to cloud for other steps — so a "zero-egress
  local" claim introduces a *new* divergence, not a saving. **Reserve local-model justifications for
  genuine sovereignty/PII needs or truly high-volume continuous inference; for an occasional batched job,
  price the cloud call first — it's almost always trivially cheap, and "local for cost" should be
  pressure-tested out.** (When the user challenges a "we need local" assumption — "do we actually need
  local or can we just use cloud?" — re-derive from the cost arithmetic, don't defend the spec.)

### 2. Fan-out sizing — scale workers to complexity *(multi-agent ≈ 15× the tokens)*
Multi-agent fan-out costs roughly **15× the tokens of a single chat** (measured, 2f). It
buys *coverage of genuinely parallel work* — nothing else. Right-size against the brief:
- **Simple fact** → 1 worker / 3–10 tool calls. (No fan-out. 2i-T4 answered a version+history
  question with **1 worker, $0.37**.)
- **Comparison / "state of X"** → 2–4 workers / 10–15 calls each.
- **Broad landscape / deep-dive** → up to ~10 workers on **distinct** angles (use STORM facet-gen
  so coverage is engineered up front, not discovered late). Cap facets at 5–7.
- **The anti-pattern:** manufacturing parallelism. Don't split a serial, single-owner task
  into N lanes to "use the swarm" — over-slicing a shared-core change is thrash, not speed.
- **Empirical anchor (2i battery):** real right-sized research runs cost **$0.37–$1.07/task**,
  peak context **68.5k/272k**. If a "simple" task is heading toward $5 or 150k context,
  something is mis-sized — stop and re-scope.

### 2b. Adaptive fan-out & upstream-429 backoff *(AIMD lease-cap)*
Fan-out width shouldn't be a fixed guess when a provider starts pushing back. The AIMD
controller in `scripts/next_lease_cap.py` (pure fn, ported from gbrain, MIT) adapts a
concurrency cap from window stats. **Decision tree, in priority order:**
1. **Ramp DOWN** — *only* on **upstream** pushback (provider 429s/min over threshold **OR**
   latency unstable). This is the **only** shrink trigger.
2. **Ramp UP fast** — workers starving (fan-out slots all taken, no upstream 429s, latency stable).
3. **Ramp UP slow** — utilization high, no pressure (probe for headroom).
4. **Deadband** — mixed signals: don't move.

**The load-bearing lesson (don't get this backwards):** shrink the cap *only* on **upstream**
pushback — never on **internal** queue bounces. An internal bounce means "workers want more
slots" (ramp UP), not "back off." Conflating them craters the cap during healthy bursts.
Mapping to our world: "upstream 429s" = `claude-api-proxy`/failover provider rate-limit errors;
"lease bounces" = subagent tasks blocked waiting for a fan-out slot; "latency_stable" = p95/p50 < 2
on recent task durations. The AIMD asymmetry (ramp-down 3 > ramp-up 1) means a 429 burst backs
off fast and recovers slow — intentional: under-fan beats hammering a 429-ing provider.

> **STATUS: tested-but-UNWIRED pure function.** Our single-orchestrator fan-out doesn't yet
> produce a `WindowStats` (no live extractor for 429-count / bounces / utilization / latency).
> The *function + doctrine* ship now; the signal source is `fleet-doctor` (future) or a fan-out
> telemetry hook. Even without the automated loop, the **ramp-down-only-on-upstream-pushback**
> rule is usable by hand when you notice a provider 429-ing mid-fan-out: narrow the width, don't
> widen it. Defaults in the module are `# UNTUNED` — calibrate on first real use.

### 3. Context budget — be deliberate, not capped *(soft guidance)*
> No hard token ceiling. Modern models (e.g. claude-fable-5/mythos-5 at 1M, opus-4-8 at 1M)
> genuinely support large windows, and Hermes resolves their real context length. Use it when
> the task warrants it. But large context = real money ($10/M in, $50/M out on fable-5) and
> degraded recall past a point — so spend context *on purpose*, not by accident. The habits below
> keep big runs cheap and clean whether you're at 50k or 500k.
- **Plan-to-scratch FIRST.** Write the brief + plan + skeleton to a scratch file *before*
  fanning out, so a long run survives a context truncation (you can re-read the plan, not
  re-derive it). This is the single cheapest insurance against a blown run.
- **Keep worker briefs tight** — a bloated brief is paid for on *every* worker. No acronyms,
  no shared context they can't resolve alone, an explicit effort budget per worker.
- **Compress before synthesis, not after** — clean/cluster raw gather output before it reaches
  the writer, while the context is still clean. Compressing after the context is polluted is
  too late.
- **Aggregate context budget, not just per-item.** Cap the *total* context you load, not only
  each file. (Borrowed from the Rust claw-code harness: it enforces a 12k-char total cap across
  ALL instruction files, 4k/file — the aggregate cap is the discipline most context-loading
  lacks.) Apply the same to multi-doc reads: know your total before you load.

### 4. Stop conditions — more search ≠ better *(anti-rabbit-hole)*
- Hard caps: simple = 2–3 searches, complex ≤ 5, **always stop at 5**. Stop if the last 2
  searches returned similar info.
- Depth past a point *degrades* accuracy (~42% in studies) — the dominant long-form error is
  over-association of unrelated facts, not classic hallucination. A few well-verified sources
  beat a pile.
- **Sufficiency-first:** stop when the brief is answered, not when you're "out of ideas." 2i-T4/T5
  both terminated on earned sufficiency, not exhaustion.
- **A DECISIVE early datapoint ENDS the measurement — don't run a full sweep to confirm a call it already
  settled.** When a gate has a threshold and the first real reading clears it by a wide margin, the
  decision is made; continuing to benchmark is busy-motion, not rigor. (2026-06-26: a prefill/decode sweep
  was set to run ~3h across 3 quants x 5 contexts to decide "build the bridge?" — the very first point,
  prefill_frac 0.918 @8K vs a 0.20 gate, already screamed BUILD. the user pushed back that spending 3h to
  re-confirm obvious value was stupid — correct. Kill the run, capture the verdict + any cheap byproduct
  already in hand, proceed.) Before launching a long verification ask: is there a single reading that would
  settle this, and do I already have it? If a multi-arm sweep ALSO answers a still-open second question
  (here: per-quant max-context), keep only the arms that answer it, drop the rest. Distinguish
  DECISION-GATING measurement (stop once the gate flips) from CALIBRATION measurement (needs the spread) —
  only the latter earns the full sweep.

---

## The pre-flight (decide these THREE before a big task)
Before a fan-out or long run, write to your scratch file:
1. **Model split** — which tier for lead/synthesis/verify vs. workers? (Default: Opus lead,
   gpt-5.5 workers.)
2. **Worker count + the budget per worker** — how many, and roughly how many tool calls each.
   An *unbudgeted* worker is how three workers redundantly chase the same sub-question.
3. **The ceiling plan** — what's the expected peak context, and where's the scratch file if it
   truncates?

If you can't answer all three, the task isn't scoped enough to fan out yet.

## The in-flight checks (watch while you run)
- **Context bar climbing toward ~180k?** Don't push — **compress, or hand off.** Write a
  `STATE.md` (plan + skeleton + in-flight decisions + what's left) so a fresh session resumes
  cheaply instead of you spending the last 20k tokens degrading. (See `handoff-doc` for the
  STATE.md long-run resumability variant; `structured-handoff` for typed fan-out returns so a
  truncated run isn't a total loss.)
- **A lane came back thin/redundant?** Kill it — note it low-confidence, don't re-spawn to
  "fix" it (re-search means a lane underdelivered; surface that, don't paper over it).
- **About to re-research during synthesis?** Stop — if the gather schema was clean, the merge is
  mechanical. Re-searching mid-write means the gather was incomplete; note it, don't silently
  burn tokens fixing it.

## Cross-links (don't duplicate — point)
- **Evaluating a token-savings / context-compression TOOL before adopting it** (rtk, headroom, any
  (savings AND correctness) eval doctrine, the "reversible ≠ safe / measure the retrieval-when-needed
  rate" rule, and the 6 recurring FALSE-GO review blockers (gameable oracle, uncalibrated judge,
  single-run noise, savings-ignoring-retrieval-cost, unverified containment, audit≠install) + per-tool
  verdicts. Read it before re-evaluating this class of tool. **2026-06-17 UPDATE in that file:**
  headroom's CCR retrieval PASSED 15/15 in active-bridge tool-loop mode (reversing the 2026-06-13
  static-mode "discipline failed" finding — "reversible≠safe" is mode-dependent), and a Layer-1 NO-GO
  can be a whitespace-brittle oracle artifact (compressor reformatted the byte, fact NOT lost) — read the
  failing trials and split real-fact-loss from cite-format-mismatch before blocking a tool. **2026-06-17(b)
  ECONOMICS verdict added:** native compress-then-expand strategies are HOLD on both haiku AND gpt-5.5
  because the model expands ~90% (paying compression + full-fetch on nearly every call → net-negative;
  mix-sweep `always-lose-in-sweep`). Key reusable lessons in that file: measure the EXPAND RATE first (a
  high one structurally kills the saving); accuracy ≠ selectivity ≠ economics (gpt-5.5 was more accurate
  but NOT more selective — report them as 3 separate rows); and the **expand-detection predicate is a
  the **expand-detection predicate is a trust root** — adversarially probe it (wrapped-shell + interpreter-glued relative reads under-count and
  fake a "selective!" result) and gate the run commit to descend from the predicate sign-off (AC6 git-DAG)
  BEFORE any measurement spend; verify the run JSON against raw trials, never the worker summary. **The B0
  COST-BASIS is a SECOND trust root in the same harness:** swapping in a NEW compressor adapter that lacks
  the native marker makes the imported measure_b0_task price the expand-roundtrip on an EMPTY payload
  (~28.6× under) → nulls the op-win penalty → fake-green YES; fix with a B0-only marker-emitting wrapper +
  a per-row regression guard, keep the live view pure, and confirm the penalty is live on a no-spend dry-run.
 - **Headroom economics MEASURED → robust NO** (2026-06-17, gpt-5.5/low):
   *perfect* selectivity (model expanded ONLY when needed: 9/9 cite, 0% summary). Lesson:
   SELECTIVITY ≠ ECONOMICS (a full-re-read expand has the same structural economics whether the model
   is selective or not); always check if a NO is *robust* (break-even 9.0% < even the Wilson-LOWER
   expand bound 14.2%, not just worst-case); the one lever that flips it is cheaper RANGED recovery,
   not less compression. Plus the backgrounded-eval interpreter-pinning gotcha.
 - **Compression activation: traffic-shape + ranged-recovery closure** (2026-06-17):
   is the CONVERSATION RE-SEND (~13K fixed), not the payload (~6-8K) → ranged/partial recovery is a
   NON-LEVER (even fetching the bare decisive line still loses); don't build it. (2) Reduce "should we
   activate" to ONE number: token-weighted cite-critical fraction of real `turns.db` traffic vs a frozen
   flip threshold (here 17.1%). THE CALIBRATION TRAP: a naive "any verbatim reuse = cite" classifier
   over-counts ~3× because 69% of reused tokens are paths/slugs a compressor PRESERVES, not droppable
   facts — band it [strict, calibrated, ceiling], audit a sample by eye (a 70% reuse rate is the tell).
   the orchestrator agent calibrated 25.4% > 17.1% → still NO, but coding traffic is the worst case (28%).
- **LCM recall-gate harness correctness** (driving a live agent through a bury→recover loop to
  — the **read/write split-brain** fake-FAIL (a `--lcm-db` flag that redirects the evidence READER
  but not the gateway's WRITES → 100% VOID on an empty throwaway db; tell = 0-byte db; fix =
  export `LCM_DATABASE_PATH` into the child env), VOID-redraw-vs-real-miss + VOID hard-stop,
  cold-start `node=None` (DAG not warmed, not a bug), never run a fixed-store arm concurrently
  with a live-store arm on one gateway, and `MAX_USD` is baked into the launched shell (bump =
  relaunch + re-reset baseline; size to OBSERVED burn — Haiku full-bury ran ~$0.20/min, 1 order
  above estimate). Generalizes: any harness flag that "isolates" a datastore must redirect the
  WRITE path the system-under-test uses, not just the reader you control.
- **Measure the spend:** `blackbox-turn-telemetry` (`/cost`, per-turn cost/token/tool cards).
- **Where the fan-out/stop rules live operationally:** `deep-research` §2 (scale-to-complexity),
  §3 (source-routing pre-brain), §7 (stop conditions).
- **Resumability so a truncated run isn't lost:** `handoff-doc` (STATE.md long-run variant +
  portable baton), `structured-handoff` (typed `delegate_task` returns).
- **Multi-agent failure modes** (over-spawn, info-withholding): `mast-failure-modes`.

## Pitfalls
- **"It has a budget flag" ≠ "it budgets."** Interface parity isn't property parity — verify the
  enforcement, not the schema. (The Rust claw-code harness plumbed a `dangerouslyDisableSandbox`
  flag through its whole type system while enforcing *no* sandbox — a perfect cautionary tale.)
- **Don't pre-optimize a cheap task.** The discipline is for tasks big enough that the spend
  matters. A 30-second lookup doesn't need a pre-flight; spending tokens deciding how to save
  tokens is its own waste.
- **Cheap-but-wrong is the worst outcome.** Cost discipline never means under-resourcing a task
  that genuinely needs the workers/model — it means not over-resourcing one that doesn't. Right
  is the first goal; cheap is the second, not the only.

## Provenance
SOUL §13 (the orchestrator agent) / §14 (the research agent) cost-and-token awareness · `deep-research` cost/stop-conditions
sections · the 2f research-agent survey (~15× tokens for multi-agent fan-out) · the 2i planted-trap
battery (real right-sized per-task costs $0.37–$1.07, peak 68.5k/272k) · the aggregate-context-budget
idea from the Rust claw-code harness review (`rust-cc-ingest-review.md` §3.3) · global token-awareness
policy. Built 2026-06-11 as part of the agentic-absorption line-124 close-out.

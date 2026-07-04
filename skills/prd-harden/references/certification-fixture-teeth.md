# Certification fixtures & self-tests that actually have teeth

When the artifact you're hardening **is itself a regression net / certification harness / gold-set
gate** (a thing whose whole job is "fail loudly when the protected behavior regresses"), the
adversarial pass turns inward: *does the gate actually red when its invariant breaks?* A
certification harness that passes vacuously, non-discriminatingly, or via coincidence is worse than
no harness — it green-lights a cutover against nothing while looking like proof.

Proven 2026-06-11 building the siftly-ace §6a gold-set certification harness + the HN crowd-signal
scorer change. **Three distinct teeth-failures, all in one build, all of which a "4/4 bars PASS" run hid:**

## 1. A bar/assertion that can't be made to RED is unproven — and global-state mutation can't isolate it

The harness had a "mutation matrix": for each of 4 bars, perturb the engine so EXACTLY that bar
reds, proving the bar's wiring fires. The first design mutated **engine globals** (`BASE`,
`OFF_TOPIC_PEN`) to force a violation. It couldn't isolate: zeroing `OFF_TOPIC_PEN["off"]` to break
bar1/bar4 also lifted an *unrelated neutral* over the gate → red **bar3** too. Cross-bar leakage =
the bar's teeth are unproven.

- **Rule:** to prove bar N has teeth, perturb ONLY bar N's input, leaving every other item
  untouched. Mutating a shared global can never isolate — it moves every item that reads that
  global. **Inject ONE forced-score synthetic probe of the target class** *after* all real items
  score through the **unperturbed** engine, and set the probe's output directly. No real item moves;
  no other bar can spuriously flip.
- **The only permitted co-red is a documented logical entailment.** Here `bar1` (no known_bad ≥
  TOP_GATE) strictly *implies* `bar4` (no known_bad > weakest known_good) **iff** `min_good <
  TOP_GATE`. So `--mutate bar1` correctly reds `{bar1, bar4}`. **Don't fake isolation** by special-
  casing it away — assert the entailment explicitly, and **derive its direction from live state**
  (compute `min_good` vs `TOP_GATE` at runtime), because a constant-shift elsewhere (the HN crowd
  term lifted `min_good` above the gate mid-session) **flips** which bar entails which. A hardcoded
  `{bar1,bar4}` assertion rots silently the moment the corpus scores shift.

## 2. Vacuous pass — an empty/hollow fixture satisfies every "no X violates" bar trivially

All four bars were phrased "no known_bad ≥ TOP", "every known_good ≥ ALSO", etc. An **empty corpus
satisfies all of them vacuously** (no item to violate them) → exit 0 → "cert passed" against
nothing. A truncated fixture (bad merge, write error) would silently green-light a cutover.

- **Rule:** any gate built from universally-quantified "no X violates Y" bars needs a
  **non-emptiness / population floor**: assert a minimum real-item count AND ≥1 of each class the
  bars range over (here `MIN_CORPUS=10`, ≥1 each of known_good/known_bad/neutral), else FAIL loud
  with a visible line. Name the threshold a constant, set it *below* the curated fixture size so
  legitimate pruning is allowed, and lock `MIN_CORPUS < len(manifest)` in a test so a future bump
  above the corpus can't silently land. Synthetic/mutation probes must NOT count toward the floor.
- Same family as the SKILL.md "silent skip on missing dependency" anti-pattern — a vacuous pass is a
  silent skip wearing a green badge.

### 2b. The vacuous-pass also bites an INTEGRITY gate over GENERATED OUTPUT when the feature is ABSENT

The same hole sinks a *publish gate that validates a rendered artifact's internal links/structure*,
not just a gold-set harness. The gate enumerates the feature's elements and checks they're
consistent — but if the feature DIDN'T RENDER AT ALL, there are zero elements, zero inconsistencies,
and the gate passes on nothing. The artifact ships missing the whole feature.

Worked example (2026-06-13, youtube-notebooklm anchored citations — "the v4 incident"). A report's
publish gate was `check_anchor_integrity(html)`: "every body `[n]` link resolves to a Sources row id
and every back-ref resolves to a body occurrence." It returned `ok:True` on a report that had
**Sources rows but ZERO clickable `<a class="cref">` anchors** — because no anchors means no forward
links means nothing dangles. The anchor renderer had silently no-op'd (the report was built minutes
before the anchor code landed); the gate waved it through; the un-anchored report shipped live and
the user caught it by eye. A green integrity check certified an artifact missing its headline feature.

- **Rule (presence floor for output gates):** an integrity/consistency gate over generated output
  must also assert the feature is PRESENT when it should be, not only that present-elements are
  consistent. Tie presence to a structural precondition the artifact already carries: *"if the
  output has Sources rows (`id="cite-G{g}"`), it MUST also have clickable anchors (`class="cref"`),
  else FAIL via an explicit `unanchored_sources` flag."* The precondition (rows exist) proves the
  feature *should* be there, so the floor doesn't false-fire on a legitimately feature-free artifact
  (a citation-free report has no rows → guard stays silent). Pair the two tests: `rows-without-
  anchors → RED` (RED-proven by stripping every `class="cref"` from a clean report) AND `no-rows-no-
  anchors → still OK` (the scope guard, so the floor isn't over-broad).
- **Why a seam-level unit suite missed it:** the format/render functions had full unit coverage and
  were green — but nothing drove the *whole* `generate()` → gate path end-to-end, so a wiring/timing
  regression (feature absent at the integration boundary) was invisible to every test. The durable
  fix was TWO things: the presence floor in the gate AND an e2e through the real pipeline asserting
  the feature appears in the actual output (see SKILL.md rule #2 "E2E wherever a real path changed").
  A gate hardened against its own vacuity is necessary but not sufficient — you also need one test
  that exercises the producer end-to-end so "the feature didn't render" can't slip the seam.

## 3. Non-discriminating assertion — passes on arithmetic coincidence, not the structural guarantee

The "off-topic content never gets promoted" safety test asserted only `final < ALSO_GATE`. But the
crowd-signal term was **not topic-gated** — an off-topic 5,000-pt story still received the full
crowd lift; it scored under the gate only because `base + lift − OFF_TOPIC_PEN` happened to land
low. **The test passed for the wrong reason.** Raise any base/substance value later and off-topic
content silently becomes promotable, and this test won't catch it — it was never testing the
property it claimed.

- **Rule:** assert on the **mechanism's own output**, not a downstream rollup that can be satisfied
  by unrelated arithmetic. Here: gate the crowd term structurally (`if is_target_branch and
  off_topic: term = 0`) and assert **the term itself is 0**, not just that the final score is low.
  Then it's discriminating: revert the gate → the term is non-zero → red.
- **The discrimination test is "revert the guard, does it red?"** A monotonicity check on a
  *rounded* final (`int(round(...))`) can tie two distinct inputs and pass; assert strict `>` on the
  **un-rounded breakdown term** instead. A knee/threshold test should pin the real boundary value
  (`assert term_at_234 >= 5` drives TOP), not just the sign of the effect (`>= 1`).
- **Pair every "must be 0/gated" test with a "must NOT be 0" scope-guard** so an over-broad future
  fix (gating *everything*, not just the off-topic case) also reds. One test pins each side of the gate.

## How to run the inward pass

For a harness/fixture/self-test, before declaring it hardened:
1. **Teeth check per assertion:** can you make each one RED by perturbing only its own input?
   Watch it fail. An assertion you've never seen fail is a claim, not a guard. (Build a `--mutate`
   matrix or equivalent; run it as a real test, isolated, asserting *exactly* the expected red set
   derived from live state.)
2. **Vacuity check:** does the gate pass on an empty / single-class / hollow fixture — OR (for an
   output/integrity gate) on output where the checked FEATURE is entirely absent? If yes, add a
   population floor (harness) or a presence floor tied to a structural precondition (output gate).
3. **Discrimination check:** does each assertion target the mechanism's own output, or a downstream
   rollup that unrelated arithmetic could satisfy? Revert the guard the assertion protects and
   confirm the assertion reds; if it stays green, it's non-discriminating — re-point it at the
   mechanism (the breakdown term, the parsed field, the structured value) and pair with a scope-guard.
4. **Wire it into the gate:** if the harness has its own test suite, fold it into `verify` (the
   Python suite here was *not* in `npm run verify` until this build — a gate the gate-builder forgot
   to run). A certification harness nobody runs is the most vacuous pass of all.

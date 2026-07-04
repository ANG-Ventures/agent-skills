# Gold-set / eval-gate design for label-driven scorers

Use this when a PRD adds an **objective acceptance gate** over a system that scores,
ranks, classifies, or filters — especially "model emits labels, code computes the
number" pipelines (the deterministic-scorer pattern). These are the traps that
recur; they were all caught (and the fixes verified) across a 4-pass Opus review of
a gold-set certification PRD.

## The instrumentation gap is THREE problems, not one
A "we have a gold set but the gate can't run" symptom almost always decomposes into:
1. **The gold items carry the human verdict (`known_good/known_bad/neutral`) but NOT
   the model's INPUT labels** (`content_type/actionability/substance/on_topic`, etc.).
   Score them as-is and every item coerces to the safe-default → meaningless scores
   (a known_good lands below the gate not because the scorer is wrong but because it's
   unlabeled). The gold set must carry the *ideal input labels* a perfect classifier
   would emit, so the gate tests the **scorer**, not the labeler.
2. **The gold set is `status: DRAFT` / never ratified.** A frozen eval fixture needs
   an explicit owner ratification step; don't treat a draft as the gate.
3. **No harness exists** — the "pass bar" is prose in a JSON `_meta` block, nothing
   executable scores the set. Grep `scripts/ e2e/ __tests__/` for the fixture name; a
   zero-hit means the gate is aspirational.
Diagnose all three before writing the fix; a PRD that only labels the items still has
no runnable gate.

## Ideal-labels invariant (isolates scorer from labeler)
The gold labels are the labels a *perfect* classifier would emit for each text,
hand-assigned + owner-ratified — NOT the labels a live model run produced. This makes
a gate failure unambiguous: "the scorer mis-placed a correctly-labeled item." Certifying
the labeler is a *separate* eval; don't conflate them.

## Run the REAL pipeline, assert on SCORE not placement
- Call the production selection function (`select_shadow` / the real ranker), not a
  reimplementation that drifts. Placement bars need the full pipeline (dedup,
  forced-distribution, slot caps, floor guards).
- **But assert each bar on the item's final SCORE, not on which slot it landed in.**
  Slot caps (MAX_TOP/MAX_ALSO) on a small fixture can *evict* a high-scoring item from
  placement, so a placement-framed "no bad item in TOP" reads green while a bad item
  that *scored* TOP-worthy (the actual regression) is live. Frame bars as "no known_bad
  has `final ≥ TOP_GATE`", "every known_good has `final ≥ ALSO_GATE`", etc.

## The gate must have TEETH — mutation matrix, one per bar
A single mutation ("zero the off-topic penalty, assert it goes RED") only proves the
harness *can* fail — it does NOT prove all N bars are wired. Three bars could be
always-true (miswired) and the suite stays green forever. Require **one mutation per
bar, each asserted to red EXACTLY its target bar**, and run each mutation in its **own
subprocess** so an in-memory constant perturbation can't leak into another case or the
clean run. (Once each mutation is subprocess-isolated, a separate "no-leak" assertion
is vacuously true and is theater — drop it; subprocess isolation IS the guarantee.)

### Mechanical-adversary rule: the mutation set is CODE, never an author-listed set of strings
When the gate's whole credibility is "the loosening I just made didn't buy back a wrong
answer," the mutations that prove it MUST be **generated mechanically from (item, source)
by a committed function** — `mutations(task, raw) -> set[str]` — not a handful of strings
the same author who wrote the fix hand-picked. A hand-listed mutation set is unfalsifiable
by construction: the author who chose the loosening also chooses the test that "proves" it
safe, and will (even unconsciously) pick mutations the fix already rejects. An Opus review
will (correctly) BLOCK an "enumerated mechanically" claim whose actual mutations are four
illustrative literals baked into the doc/test. The enumerator must:
- emit (a) **drop** the decisive token, (b) each declared `forbid[]` alternative, and
  (c) the **nearest confusable(s) present in the SOURCE** of the same type-class as the
  expected answer — scan SOURCE with per-type regexes (semver, file:line, http-status,
  KEY=value …), excluding the expected answer itself;
- be **field-wise across every decisive dimension** — for a `path:line` citation, generate
  BOTH same-file-different-line (`:88`) AND different-file confusables, not just one;
- be the thing the test *calls* (parametrize over `mutations(task, raw)`), so adding a new
  task auto-extends the matrix and nobody can satisfy the bar by re-typing the safe strings.
The single highest-value case is the confusable that the loosening *could* have accepted
(e.g. after adding `acceptable:["HTTP 429"]`, assert `HTTP 200` — the other status in the
source — still FAILS, caught by `forbid:["200"]`). That one assertion is the actual proof
the fix has teeth.

## Pin the gates the bars compare against (one literal)
If a future regression retunes the gate constants themselves — exactly the Non-Goal a
scorer-cert guards — the bars move with them and stay green. Define the expected gate
values as a **single literal**, feed *those same symbols* into the pipeline AND assert
the engine's own resolved constants equal them. No re-typed `49`/`45` elsewhere.

## Bar-strength honesty: name the structurally-satisfied bars
On a small incident fixture, some bars are nearly true by construction (the spam/junk
items already floor at ~0; a floor-pinned neutral can't reach TOP regardless of the
math). Say so plainly in the spec — "Bars 1 & 3 are structurally-satisfied; Bars 2 & 4
carry the real signal" — instead of dressing a synthetic-fixture mutation up as proof
the production pool exercises that bar. A reader must see which bars are live nets.

## Prove-on-proposed-DATA BEFORE ratification — and surface, don't force-green (the D-8 rule)
Before presenting the gold set for owner ratification, run the gate on YOUR proposed
labels. If a bar fails on *correctly-reasoned* labels, that is a **finding to surface to
the owner as a decision**, NOT a license to reverse-engineer labels to hit green —
reverse-engineering makes the gate certify nothing.
- The failure is usually a genuine **labeling-vs-scoring tension** the gate exists to
  expose. Worked example: two items the human gold-rationale wanted as `neutral`
  ("2 likes = no crowd signal, ALSO at most") scored TOP-worthy because the engine, *by
  design*, doesn't down-rank a thought-leader for low engagement (TL bump + low-reach cap
  is unknown-handle-only) and 36 likes clears the unknown-handle floor. Neither is a bug;
  it's a taste call: is this a label fix (the item really is `reference`, not
  `actionable_now`) or a scorer finding (you *do* want substantive low-engagement
  thought-leader content in TOP)?
- Present the fork as numbered options with a recommendation, leave the gold `status`
  DRAFT, and stop. Don't unilaterally pick — and absolutely don't relabel to pass.

## DEMOTION-GUARD / new-backstop over a label-driven POOL — the Opus-review trap cluster (2026-06-28)

Distinct sub-family: the PRD doesn't build the *eval*, it adds a **deterministic guard that
DEMOTES items the model mislabeled** (a "junk-label backstop" — crypto/scam/foreign-clickbait
demotion over a scored pool, a spam-down-ranker, any "force on_topic→off / content_type→promo
when the model got it wrong" override). Ground-truthed building Backstop-4 for the siftly
digest scorer; an Opus pass-1 came back **BLOCK** + two APPROVE-WITH-CHANGES, pass-2 converged.
Every one of these traps recurs for this class — fold them at SPEC time:

- **The precision gate is TRAIN==TEST if you tune the detector on the same pool you measure it
  on.** You author the regex/token signals by inspecting the flagged items in today's pool, then
  assert "precision = 1.0 on today's pool" — guaranteed by construction, proves nothing about
  generalization (the exact gold-set tautology, one level over). Fix: the same-day pool is the
  **tune set**; ratify a **held-out SECOND day's pool** as the binding precision gate, and report
  the holdout's **size + junk count + near-miss count** (precision 1.0 on a holdout with 2 junk
  items and no near-misses is decorative). Pre-merge out-of-sample, not a post-merge n=1 live run.
- **"Independent oracle" must label the FULL holdout CLEAN set, not just your pre-flagged subset.**
  If your second labeler (the QA agent / a QA agent / a human) only sees the items you already suspect, it
  can confirm true-positives but is **structurally blind to the FALSE positives the gate exists to
  catch.** The FP-exposure surface is the *clean* set — that's exactly what the independent pass must
  cover. (Drive a fleet QA agent over the full holdout via `argus-judge.sh`/`ask-agent.sh`; commit
  the verdict; reconcile disagreements on record.)
- **"Downgrade-only" must be BY CONSTRUCTION (a monotonic clamp as the LAST op), not a property
  test over today's pool.** A label-swap demotion (`content_type→promo`) can be an *upgrade* if some
  content_type's BASE sits below `promo` — and a single-pool property test can't see a future item
  whose true label is below it. The airtight form: `final = min(final, DEMOTE_CEILING)` applied as
  the **final write to `final`, after EVERY additive term** (PF, author, recency, media + the 0–100
  clamp). Pass-2 reliably catches the half-version: if the clamp subtracts only `PF_CAP` but author/
  recency/media are added *after* it, a demoted item re-crosses the gate. Clamp-last ⇒
  `DEMOTE_CEILING = GATE − 1` provably bounds it regardless of envelope size; pin gate inclusivity
  (`>=` floor ⇒ `−1` is strictly below). The matching AC: a **max-envelope selftest** adds the MAX
  of every additive term to a demoted item and asserts it STILL `< GATE`. (Bonus: drop any belt-and-
  suspenders label mutation the clamp already makes redundant — it's pure risk surface.)
- **"Byte-identical for the clean items" is WRONG when the pipeline has POOL-RELATIVE stages.** A
  fused personal-fit that centers on `pool_mean_embed`, an author-cap that counts per-author across
  the pool, an overview that computes salience over `all_scored` — all shift when N items leave the
  pool. So a clean item's *final score* can legitimately move even though the guard never touched it;
  an AC demanding "byte-identical final_score for the 223 non-junk" **fails on correct behavior**.
  Scope the invariant correctly: **per-item terms** (BASE/substance/engagement/author/recency/media +
  breakdown) byte-identical; the PF-coupled field NOT byte-identical → instead assert **no non-junk
  item changes its selection SLOT** (Top/Also + overview placement), and report the `pool_mean_embed`
  delta. Also conflating "unflagged" with "legitimate" is a trap: label ALL N items (not just the
  top band), because the guard may correctly demote a junk item BELOW the band that wasn't flagged.
- **Shape-detector signals are FALSE-POSITIVE MAGNETS on the benign substring — require the SHAPE,
  corroboration-gated.** `FREE … (API|GRANT|CREDIT)` nukes legitimate OpenAI/Anthropic/HF credit
  programs and hackathon grants; a lone `$TICKER` (`\$[A-Z]{2,6}`) nukes `$NVDA`/`$GOOGL`/`$AMD` in
  real AI-infra/earnings threads. Re-scope each signal to the *scam/junk SHAPE* (impersonation +
  DM-me + link-in-bio + hype emoji; cashtag AND a crypto-context corroborator) and make the legit
  counterexample a **mandatory near-miss fixture** that MUST NOT demote. For "foreign-clickbait,"
  measure by **Unicode SCRIPT CLASS, not byte-ASCII ratio** (a Turkish/Vietnamese/Indonesian
  Latin-diacritic AI post has high non-ASCII bytes but is Latin script + genuinely on-topic — must
  not trip), and KEEP any foreign post carrying a romanized model name (gpt/claude/llm/qwen/…).
  Precision-over-recall is the hard rule: better to miss one junk item (caught by the recall audit)
  than demote one real story.
- **The live proof must fire on the MISLABEL CLASS, not "any firing."** Defense-in-depth (a prompt
  rubric fix that makes the model label junk `off` itself) means the deterministic backstop fires
  *less* on future pools — so "debug dump shows ≥1 `junk_backstop` firing" can be satisfied by a
  borderline item while the real mislabel class is now handled upstream, leaving the deterministic
  layer unproven. AC must assert ≥1 firing **on an item the MODEL labeled `core`** (the actual class).
  And add the **inverse-failure LOUD guard** the user always wants: a demotion-RATE watchdog (alert
  when the per-run demote count spikes past a baseline) — silently over-demoting real items is the
  "green for 11 days" trap (see read-amplification incident) that the backstop itself can cause.
- **Reuse the EXACT existing exemption helper, don't fork it.** A new backstop over the same pool must
  call the same curated-source / fragment / off-topic helpers the existing backstops use
  (`is_topic_curated_source`, …), grep-proven — a parallel copy is a config-drift bug waiting to
  diverge. And pin the **input field contract**: state exactly which `item` keys the detector reads
  (full `tweet_text`, NOT the ≤120-char pf-audit snippet) and that it does NOT read the field that
  differs across brief shapes (`signals`), with a truncation-skew selftest so the fixture can't carry
  a different byte set than production.

## Baseline / fairness gate FIRST — test the system-under-test on a fair corpus, not a rigged one
For an eval that measures a *transformation* (a compressor, a summarizer, a retrieval
layer, any "does X preserve the answer" benchmark), the FIRST gate is not the transform —
it's the **uncompressed/untransformed BASELINE on the same corpus**. If the model can't
answer correctly even from the *full, faithful* source, the corpus/oracle is unfair and
every downstream delta is meaningless (you'd be measuring against a rigged floor). Bake a
per-item baseline-fairness gate (e.g. per-task `mean_pass >= 0.90`) that BLOCKS the expensive
transform run until the baseline is clean. A worker that blocks here instead of benchmarking
anyway is doing the right thing — that block is a finding about the corpus, not a failure.

### When the baseline gate blocks, diagnose ELIGIBILITY before touching the oracle (the relabel-to-green trap)
A baseline failure has several causes; only some are corpus defects you may fix:
- **format-variant** (answer carries the decisive fact in a different shape: `HTTP 429`
  vs `429`, `1.0.203` vs `serde v1.0.203`, prose `Line 77 of X` vs locator `X:77`) →
  genuine oracle defect; fix.
- **citation-strategy** (answer is correct, the *citation* check fails on a structural
  marker like a diff `+` prefix or a sub-floor fragment) → add an evidence/normalization
  strategy; fix.
- **ambiguous corpus** (the question has two genuinely-correct answers) → **disambiguate
  the question**, never multi-accept both (multi-accept would also pass a transform that
  dropped one). 
- **flakiness** (the item fails non-unanimously across replicates) → EXCLUDE, don't loosen;
  variance is not fixed with a looser answer key. Determinism is **empirical**, not a pinned
  param: many proxies strip `temperature`, so confirm replicate-IDENTITY in the capture
  before claiming "temp 0"; a unanimous-fail item is eligible, a split item is flakiness.

### When the WHOLE FAIRNESS GATE fails on aggregate COUNT (22/24, not 24/24) — prove noise-vs-regression with 3 tests before accepting OR blocking
A post-change re-run can return a baseline/native fairness arm at `22/24 perfect` instead of the
literal `24/24` gate, with 1-3 tasks landing at `pass_rate` 0.85-0.95 (i.e. 17-19/20 replicates).
This is the moment the orchestrator must NOT do either reflexive thing — not block the build as a
fairness failure, and not loosen the 24/24 bar. Run a positive **noise-vs-regression diagnostic**;
if all three hold, the failure is model jitter and you ACCEPT with a documented eligibility-triage
(no gate touched). The three tests (proven 2026-06-16, grep_cluster fence re-benchmark on Haiku):
1. **Corpus identity — `manifest_sha` byte-IDENTICAL across all arms.** This is what the fairness
   gate *actually* protects against (corpus drift between arms making a delta unattributable). If
   baseline / native / semantic all carry the same `manifest_sha`, the gate's real purpose is MET
   even when the literal count is sub-24/24. Drift = real problem; identical = the count is noise.
2. **Failures ANTI-correlated with processing.** Tabulate the sub-1.0 task's pass_rate across the
   arms by amount of transformation: e.g. `real-cargo-compiled-crate` baseline 0.85 < native 1.0 <
   semantic 0.9; `real-git-diff-grace` baseline 0.9 < native 0.95 < semantic 1.0. **The UNCOMPRESSED
   baseline scoring WORSE than the compressed/processed arms is impossible for a real compression
   regression** — a transform can't make the raw arm worse than itself. Anti-correlation (or random
   scatter) across arms = the model missing K/N replicates at random, not a defect. (Same-task-fails-
   identically-across-arms in the SAME direction, scaling with processing, WOULD be a regression.)
3. **The flaky task is NOT a target of the change.** The fence/fix touched the grep lane; the flaky
   tasks are cargo/git-diff (non-grep). A miss on a task the change doesn't touch can't be caused by
   the change.
The honest framing to record: "the gate's INTENT (same corpus, attributable delta) is satisfied; only
its LITERAL 24/24 count is defeated by ~2-3 stray model replicates on non-target tasks on the least-
processed arm." Per the eligibility rule above, that is a flaky genuine-model-miss → note/exclude,
NEVER lower the threshold. Optional non-blocking follow-up: a higher-N re-run of just the flaky tasks
would show them recover to ~1.0, but it is not required to certify the change. A worker that returns
`blocked=review-required` on this (rather than self-passing the sub-24/24 OR failing the build) did
the RIGHT thing — the aggregate-count ambiguity is an orchestrator gate-decision, not a worker call.

### A worker's `real-defect` (or `green`) label is a CLAIM — re-measure it against raw per-replicate data before accepting EITHER direction
The verification gate cuts both ways: don't rubber-stamp a worker's "green," and equally don't rubber-
stamp a worker's "real-defect"/"blocked" escalation. A higher-N re-run worker returned
`real-defect: real-cargo-compiled-crate baseline 37/40=0.925 <0.95, stop activation` (2026-06-16). The
"defect" label was wrong, and reading the **raw per-replicate failures** proved it in three reads:
1. **Which ARM failed?** The miss was on the **baseline (uncompressed)** arm; the **native (compressed)
   arm scored 39/40 — BETTER**. A compression/fence change cannot be the cause of a baseline-arm miss,
   and a compressed arm beating baseline is the opposite of a compression regression.
2. **Is the failure CONSISTENT (defect) or SCATTERED (jitter)?** Tabulate the distinct wrong answers:
   all 3 misses gave the identical `v1.0.203` vs expected `serde v1.0.203`. A single recurring
   short-form answer is not random corruption — it's the model giving a *defensible* answer the oracle
   rejects.
3. **Read the TASK, judge whether `expected` is even right.** Prompt: "Which **serde** crate version did
   cargo compile?" — the prompt already names serde, so `v1.0.203` is a reasonable short-form. This is
   **prompt ambiguity** (an eligibility "ambiguous corpus" case), surfaced by N=40 giving the model more
   chances to give the short answer — NOT a compression defect, NOT a reason to block activation.
The reflex: a worker's terminal label (`real-defect`, `green`, `blocked`) names a verdict; the raw run
JSON names the truth. Re-label against the data (which arm, consistent-vs-scattered, is `expected`
correct) and record the corrected analysis on the task before deciding. The classification — jitter vs
format-variant vs ambiguous-corpus vs genuine-miss vs real-regression — drives an entirely different
next step, and the worker often picks the alarming one.

### A frozen-corpus / oracle / threshold DECISION is a TRUST-ROOT call → route it to the user with numbered options, do NOT fix-to-green unilaterally
Beyond *certifying a loosening* with a non-author (below), the **decision of whether to loosen at all**
on a frozen corpus / oracle / gate threshold belongs to the user — it's the same trust root the whole
benchmark rests on, and the user's standing preference is that these come to him, not get silently resolved.
When an eligibility-triage lands on "ambiguous corpus / format-variant" (a genuine fork), present it as
numbered options with a recommendation and STOP — do not pick unilaterally, and never relabel-to-green.
The canonical fork (proven 2026-06-16): **(1) accept-as-is + document the exclusion** (when the gate's
INTENT is met and the change is provably not at fault); **(2) fix the PROMPT not the oracle, then
re-freeze the corpus + non-author re-cert** (cleanest, but corpus churn + a mini-cert cycle); **(3) fix
the `expected` to multi-accept** — flag this as oracle-loosening-adjacent and resist it (multi-accept
would also pass a transform that dropped one of the two answers, defeating the gate). Recommend (1) now
with (2) as cheap follow-up when the change is not the cause; the orchestrator coordinates and verifies,
but the user makes the trust-root call. (Same family as the D-8 "surface, don't force-green" rule and
the non-author-cert separation-of-duties below — applied to the *decision*, not just the *certification*.)

### The load-bearing gate is RECOVERY-via-the-claimed-route, not the aggregate mean — verify it per-task
When a benchmark's whole point is "the change makes failing tasks recover," the certification is NOT
"mean_pass went up" — it's **each target task recovered AND took the route the change claims**. For a
fence that routes grep to the lossless lane, the per-task proof is a tuple: `pass_rate 0.000→1.000`
AND `compressed_chars == raw_chars` (raw passed through) AND no `strategy="grep_cluster"` substring in
the recorded view AND `wilson95_lb ≥ floor`. A `char_tuples` of `[134,134,134]` (raw==compressed) is
the positive route-proof; a number copied from the STALE pre-change run does not count — the run must
post-date the change. Verify this per-task yourself from the raw run JSON; the aggregate mean can be
green while a target task recovered for the wrong reason (or didn't recover and got masked).
- **genuine model miss** (decisive fact actually wrong/absent in the answer) → EXCLUDE;
  fixing the corpus to accept a wrong answer is the cardinal sin (relabel-to-green) — the
  gate then certifies nothing.
Drive eligibility from an **evidence-first capture** (the real per-item answer/reason/
replicate-identity), never a predetermined "they're all just oracle bugs" conclusion stated
in the draft — an Opus review will block a PRD that asserts its own finding.

### Edit the corpus SOURCE-OF-TRUTH, not the regenerated artifact
A frozen eval corpus is often *generated* by a builder/freeze script (`freeze.py` emits
`real.json` + a combined `MANIFEST.sha256`). Editing the generated JSON then running freeze
**clobbers your edits**. Find the builder (grep the corpus for a task's literal text — it
lives in the script's row table), edit the builder, regenerate, and let the manifest re-hash
from the script. The manifest is a single canonical hash over ALL corpus files combined, so
`shasum onefile` ≠ the manifest value — verify with the freeze script's own `--check`, not a
hand hash.

### Non-author certification for a TRUST-ROOT loosening (separation of duties)
The oracle/gate is the control the whole benchmark rests on. The party who *benefits* from it
clearing (the author whose blocked task proceeds once it's loosened) must NOT be the party who
certifies it still has teeth — that's the same self-grading the mutation-matrix rule fights,
one level up. Route the final certification (mutation matrix + post-fix gate re-run) to a
**non-author** (a QA-profile agent / a senior-review gate) from a **clean checkout**; have it
re-run `score()` itself against each confusable rather than trusting the author's green. Drive
a fleet QA agent via CLI (`hermes -p <qa-profile> chat -q "..."`) and have it write a
certification artifact (commands + outputs + verdict) into the repo. the orchestrator agent coordinates but
does not self-certify a trust-root change.

### The verdict was measured at the ADVERSARIAL operating point — compute the BREAK-EVEN / crossover before accepting "X fails" (2026-06-17)
The most dangerous benchmark result is one whose numbers are all *internally correct* but whose
**verdict is an artifact of the corpus's operating point**, and where the *decision-relevant* number
was never computed. Worked example (compression economics bake-off): a worker reported
`operational-win: NO — both native strategies FAIL`, with every token count tying out and the corpus
sha frozen. The "FAIL" was computed at the **Phase-2 corpus's observed 100% expand rate** — but that
corpus is **adversarial by construction** (every task buries a must-cite-verbatim fact, which *forces*
an `expand_artifact` on every trial). 100% expand is the worst case, not the operational case; at 100%
expand you pay for the compressed view AND the full raw payload, so of course it goes net-negative.
The number that actually decides activation — the **break-even expand rate** `p* = (raw − compressed) /
(expand_inclusive − compressed)` — was never in the report. Computing it (diff ~58%, log ~75%) flipped
the story from "compression fails" to "compression nets positive whenever real expand rate < 58-75%."
The reflexes, for ANY transform/benchmark whose cost or quality depends on a *frequency* the model
chooses (expand rate, retrieval rate, fallback rate, escalation rate):
1. **Identify the operating point the verdict was computed at, and ask if it's the corpus's RIGGED point
   or the realistic one.** An adversarial corpus built to stress correctness (force the expensive path
   every time) is the WRONG corpus to read economics off — it's a worst-case fixture, not a traffic
   sample. A verdict at the worst case is a worst-case verdict, not THE verdict.
2. **Compute the break-even / crossover yourself and report where the realistic operating point sits
   relative to it.** "X loses at the 100% point" is not a decision; "X breaks even at p* and the realistic
   rate is plausibly below p*" is. Make the gate emit the crossover as a first-class number, not a buried
   implication. (In a spec, this becomes a CONDITIONAL recommendation — "win iff real rate ≤ X*" — never
   an unconditional pass/fail from a single rigged mix.)
3. **The gate constants must be RE-DERIVED from the corpus under test, not inherited.** If break-even was
   estimated once and then used as a gate input, it is an *unaudited constant*. Re-derive it from this
   corpus's own cost basis, sha-pin the inputs, and report `(prior, re_derived, delta)` — a large delta is
   itself a finding that should PAUSE the verdict, not proceed-with-a-warning. A gate keyed to an inherited
   number is an unaudited gate (config-in-all-but-name).
4. **Use the CONSERVATIVE bound on both the rate AND the per-trial cost.** Expand/round-trip cost is
   trial-variable (depends on what the model expands), not a scalar — aggregate it with a CI and a stated
   worst-case, and require net-positive at the rate's *upper* CI bound AND under worst-case cost before
   greening. A mean-vs-mean point comparison hides the tail that flips the verdict.
5. **The measured frequency is MODEL-SPECIFIC.** An expand/escalation rate measured on a cheap eval model
   (haiku) does not generalize to the production model whose discipline differs — label it, and make
   production re-measurement a named activation precondition, not an asterisk.
This is the economics analogue of the baseline-fairness gate above: there, you test the uncompressed
baseline on a fair corpus *before* the transform; here, you read the transform's economics at the
*realistic* operating point, not the adversarial one the correctness fixture forced.

### Uniformly LOOSENING a trust-root oracle relaxes it for EVERY contender, not just the one you meant to rescue (2026-06-17)
When a fix is "normalize the oracle so contender A stops failing on a byte-format technicality" (e.g.
whitespace/JSON-minification differences in a verbatim-cite check), applying that normalization
*uniformly* (correct for fairness — never a contender-specific branch) also relaxes the gate for the
contenders that were *already certified under the old stricter oracle*. A previously-certified native
arm can silently move (34/35 → 35/35) under the looser oracle, and that movement is a real change to a
ratified result — not a free upgrade to absorb. Two guards: **(a)** report each already-certified arm's
pass-count under BOTH the old and the normalized oracle (or assert byte-identical); any MOVED verdict is
a hard stop for the verification gate, surfaced as "a normalization rescued contender A but also moved
B's certified result," not a footnote. **(b)** Prove uniformity by an INVOCATION COUNTER in the run JSON
(native + baseline + the rescued arm all traversed the normalized path) — a grep for "no contender
branch" is necessary but not sufficient, because a contender-agnostic *function* can still be *called*
only on the rescued arm's tasks via the `evidence_strategy` assignment. And per the non-author-cert rule
below: the oracle is the trust root, so the senior diff-review of the loosening must gate **before** the
measurement phases spend their budget (fail fast on the trust root), not at memo-acceptance time after
the expensive runs already consumed the looser oracle.

## Closing a keyword/heuristic-classifier accuracy gate against REAL user data (2026-06-18)

The methodology above is for a fixed corpus. When the gate is "does this classifier label real
purchases / tickets / records correctly enough" and the **gold labels must come from the human**, this
end-to-end workflow worked (Purchase-Tracker AC-C2 — 87 real purchases, passed 0.816 honestly):

1. **Deliver the label sheet as an ENRICHED spreadsheet, not a bare list.** The human can only label
   well with the salient context. For purchases that was date + $ total + #items + the FULL (untruncated)
   item text — a Google Sheet (`sheets create`/`update`, `drive share --type anyone --role writer`), one
   `YOUR LABEL` column they fill, the classifier's guess in an adjacent column, sorted by guess so similar
   items cluster. The user explicitly asked for "salient info so I can actually decide" — a bare item name
   is not enough. Pre-seed the gold label to the guess so confirming is a no-op; keep the guess under its
   OWN key so `grade()` never scores the classifier against its own output.

2. **INSTRUMENT which keyword fired BEFORE tuning — never guess the vocab fix.** The classifier returns
   `business_hits`/`personal_hits`; print them on every miss. The real bug was almost never "missing a
   keyword" — it was **substring-trap business terms** (bare `box` matched packaging on a cutting board /
   wall hook; bare `office`/`switch`/`adapter` fired on "OXO"/"shower caddy"). Fix = specific multi-word
   forms (`shipping box`, `office chair`, `network switch`), not more keywords. (Same Iron Law as
   systematic-debugging: observe the actual hit before theorizing the remedy.)

3. **Prove you're not OVERFITTING the vocab to the visible misses.** After tuning, STRIP every
   item-specific term that could have been reverse-engineered from the test set (santa/christmas/popcorn/…)
   and confirm the gate STILL clears the floor on general category words alone. If it only passes with the
   reverse-engineered terms, you overfit — that's the relabel-to-green trap wearing a vocabulary costume.

4. **SEGMENT the residual into structurally-undetectable vs fixable, and report the CEILING.** Some misses
   can NEVER be classified from the available signal — a grocery "toilet paper" order that's actually a
   *business meal expense* looks identical to a personal one from item text. Those are HONEST misses
   against a deterministic rule, NOT bugs; the human flags them manually. Compute the absolute ceiling
   ("if the fixable bucket were perfect, max is 0.92 because N rows are undetectable") so the gate
   threshold is set against reality, not aspiration. Don't chase undetectable misses — that's overfitting.

5. **A user-given DETERMINISTIC SOURCE rule can conflict with their own hand-labels — surface it, don't
   auto-resolve.** "instacart → always personal" collided with Best-Buy/Target rows the user had marked
   business (the source also fulfils non-grocery retailers). Present numbered options (strict rule / rule
   with exceptions / hand-labels win) and let them pick. The gold is GROUND TRUTH (their labels); the
   source rule is the classifier HEURISTIC — where they disagree the gold wins and it scores an honest miss.

6. **🔴 Decoupling check: is the classifier's vocabulary/threshold SHARED with a money-bearing /
   irreversible path?** The bookkeeping classifier's keywords were *parity-locked* to the card-routing
   module (`payment.py`, which decides **which credit card a real order charges**). Tuning the bookkeeping
   classifier on gold data would have *silently changed live card routing*. **Before tuning ANY shared
   vocabulary/threshold, grep for its other consumers** — if one drives a live spend/actuation decision,
   DECOUPLE first (give the classifier its own copy, leave the money path's copy frozen) and add a test
   asserting the split. A parity-lock that was a feature for "keep them in sync" becomes a hazard the
   moment one side starts feeding a tunable gate.

The live `reclassify` over a money-feeding table is an append-only snapshot→restore-revertable pass;
back up the DB first, run with an explicit `run-id`, then VERIFY the money invariant (reclassified SUM ==
purchases SUM, to the cent) and the per-source rule effect before declaring done.

### The MEASUREMENT INSTRUMENT is itself a trust root — the expand/usage-detection adapter, reviewed before spend (2026-06-17)

The oracle-loosening rules above guard the *answer key*. A separate, equally-load-bearing trust root is
the **adapter that turns the model's raw run into the numbers** — the per-turn usage parser and the
expand/retrieval-DETECTION predicate. A bug here doesn't loosen the gate; it **fabricates the datapoint**
(e.g. under-counts the expand rate → manufactures a fake "this model is selective!" result you *wanted*
to see). Treat it like the oracle: senior diff-review + your own adversarial probe BEFORE any measurement
spend, AC6-style git-DAG (the Phase-B run commit MUST descend from the sign-off commit;
`git merge-base --is-ancestor <signoff> <run>` returns 0).

The expand/usage detection predicate is a recurring landmine — proven by finding TWO real false-negatives
across three review passes on ONE adapter (Amend-3, 2026-06-17), each of which would have under-counted
the expand rate:
- **Wrapped-shell commands.** The model emits its retrieval as `/bin/zsh -lc "rg pat artifact_full.txt"`;
  a naive `name in shlex.split(cmd)` misses it because the inner command is ONE token. Recursively unwrap
  `-lc`/`-c`/`-e` payloads before matching.
- **Interpreter-glued RELATIVE reads.** `python3 -c "open('artifact_full.txt')"` / `node -e "readFileSync('artifact_full.txt')"`
  — the reader (`python3`/`node`) passes the has-reader check, but the relative basename is glued INSIDE a
  string literal, so absolute-substring / `./name` / token-basename all miss it. Fix: a boundary-anchored
  relative-basename regex `(^|[\s'"/=(])<name>($|[\s'")\];|&,])` that flips both interpreter cases True
  while keeping `artifact_full.txt.bak` / `my_artifact_full.txt` / `xartifact_full.txt` / reader-less
  `echo <name>` correctly False.
The reflex: **byte-check the reviewer's claimed false-negative yourself** (reproduce it scoring `False`
against the live predicate before applying the fix), then prove the fix with a probe that includes
false-positive guards (suffix/prefix/glued near-misses), lock the cases into the unit test, and re-run a
real live smoke. A reviewer's "I found a hole" is a claim; the probe is the truth — and so is the fix's
"no over-correction."

### Opus pass-1 of a MEASUREMENT PRD reliably hits three measurement-HONESTY blockers (fold them at SPEC time)

For a PRD whose entire output is "defensible evidence" (a benchmark, a bake-off, an economics gate), the
pass-1 blockers are almost never activation-safety — they're whether the number is *honest*. Pre-empt all
three in the spec so pass-2 converges:
1. **In-sample-fit break-even (no holdout).** If the gate threshold (break-even rate, cost model) is
   *derived from the same N draw it then judges*, you're fitting and scoring on one sample — it flips on
   resampling. Fix: **PRE-REGISTER the cost model** (token prices + worst-case per-trial cost) in Phase 0
   BEFORE the run; measure only the *rate* from the run; label the verdict **in-sample**; make a
   confirm-draw **mandatory** (not "recommended") whenever net lands within one CI width of zero.
2. **N too small for the precision the gate demands.** N=35 gives a perfect-score Wilson LB of ~0.901 —
   **zero correctness error budget** (one miss fails a ≥0.90 gate) — while the rate CI is ±~15pp and the
   verdict reads off the *upper* bound. The gate is then "pre-decided by ~1 trial." Fix: compute the
   **MDE/power in Phase 0** and pre-commit an **INCONCLUSIVE → larger-N or HOLD** branch in synthesis, so
   a band that straddles zero is not forced into a PASS/HOLD.
3. **`grep` ≠ runtime isolation for a "no live side-effects" invariant.** When the measurement introduces
   an in-path actor (a proxy in front of the provider), "no live caller routes through it" proven by grep
   + config-hash proves only *static* absence. Fix: an **out-of-band process/socket check** (the actor's
   listener exists ONLY within the eval subprocess lifetime — `lsof`/process-tree during, gone after) +
   an **egress-allowlist capture** (the actor's actual connect destinations match a pre-declared list;
   off-list incl. vendor telemetry = BLOCKER). Promote both into the AC evidence list, not a footnote.
Two companion traps the same review surfaces: **cross-run cost-model identity** (the head-to-head row is
apples-to-oranges unless BOTH contenders' break-even came from the *same committed code path* — reuse by
import, prove it, don't reimplement), and **silent reasoning-token zeroing** (an older proxy/parser may
drop `reasoning_output_tokens` → undercount cost → *flatter* the contender; Phase 0 must assert reasoning
tokens are non-zero where expected, not merely that a usage object exists).

### Pass-2 of a measurement PRD finds second-order seams IN THE PASS-1 FIXES — not new design holes (2026-06-17)

The expected shape of a *converging* pass-2 (Amend-4): all providers return APPROVE-WITH-CHANGES, confirm
the pass-1 honesty blockers are GENUINELY resolved, flag ZERO activation-safety regression — and then find
that your pass-1 *fixes* introduced their own asserted-not-proven claims. Recognizing this shape is how you
know to STOP at pass-2 (the next real signal is the empirical Phase-0 probe, not a pass-3 of paper review).
The recurring fix-introduced seams, each with the tightening that closes it:
- **A "frozen / pre-registered" value frozen in NAME ONLY.** Writing the pre-registered cost model into the
  editable PRD doc is not tamper-evident, and a Phase-0 smoke that previews tokens *before* the freeze lets
  the "frozen" numbers be chosen after glimpsing the data. Real freeze = commit the value to a file whose
  commit is a **git-DAG ancestor of the run commit** (mirror the adapter sign-off's `merge-base
  --is-ancestor`), assert the runner loaded that exact file hash at verdict time, and set worst-case
  constants from first principles / a prior run — never back-fit from the smoke.
- **Two new guard mechanics that OVERLAP with no precedence → a forkable gate.** Adding both a
  confirm-draw trigger AND an INCONCLUSIVE branch (or any two borderline rules) lets an operator pick the
  branch that gives the answer they want — re-introducing the discretion the pass-1 fix removed. State
  explicit precedence (X decided first from Phase-0 power and dominates; Y reserved for the residual
  powered-borderline case), and pin the trigger to the **decision statistic** (op-win at the upper CI
  bound), not a correlated-but-different quantity (raw net tokens).
- **Identity proven at the wrong layer (function ≠ constants).** "Reuse by import, not copy" proves the
  same *function* ran, not that it got the same *inputs* — a shared function called with different
  constants reproduces the apples-to-oranges bug. Assert byte-identical inputs (frozen-file hash), not
  just shared code path.
- **A control that can pass VACUOUSLY.** An `lsof`/process-isolation check that only asserts "gone after"
  passes if it sampled at the wrong moment / the listener bound late. Require a **positive control** —
  observed PRESENT during a known-active window — so absence is meaningful evidence, not a no-op.
- **A confirm/retry described as "run again and eyeball."** Needs a pre-stated combine rule (pool draws →
  recompute the CI) or it's a second in-sample fit; and on a seedless model, don't over-claim a re-draw
  "resolves nondeterminism" — it's a fresh sample, not a replication, and reduces but doesn't eliminate
  one-draw fragility. If Phase-0 MDE says underpowered, the honest output is INCONCLUSIVE, not stacked
  confirm-draws.
- **A "defined predicate" that's actually operator judgment.** "reasoning expected", "no known
  regression", "where expected" — pin each to a concrete construction (a forced-multi-hop trial asserted
  per-mode; a named non-author reviewer sign-off), or the gate is unfalsifiable in both directions (a true
  zero looks like a strip; a real strip waves off as "not expected here").
- **A correctness-vs-economics precedence left undefined.** When the correctness gate has zero error
  budget (one miss → LB below floor) AND the rule says "a miss only *annotates* the economics," the most
  likely real outcome ("economics positive + one correctness miss") is undefined. Pre-commit: a correctness
  LB below floor **vetoes PASS regardless of economics** (lands HOLD-with-economics-recorded), even though
  the economics number is retained for the record.
- **A partial-pass / deadlock branch left undefined.** "BOTH modes must pass usage" with no branch for
  "one mode passes, the other doesn't"; "CCR gated behind closing a correctness hole" with no exit if the
  hole is unreproducible. Every multi-arm/blocking gate needs its degraded branch pre-committed (the
  working arm proceeds single-mode + the other recorded "unmeasurable"; a 3-arm CCR exit clean/drop/
  labeled-caveat) so the Amendment can't silently deadlock or drop an arm.

## Grading a SUBJECTIVE "is this TRUE about the user" gate — groundedness ≠ truth, and small-N can't power it (2026-06-26)

When the thing being certified is a model's **judgment about the user** (a user-model layer's conclusions
"the user prefers X" / "the user decided Y", a personalization classifier, a profile synthesizer), the eval has a
property the corpus gates above don't: **only the human is a valid truth oracle**, and an LLM judge can at
most grade a *different* thing. Split the arms and don't conflate them — proven building the Reflector
truth-precision gate.

- **TWO ARMS, not one. Groundedness ≠ truth.** A disjoint LLM judge (a model that didn't author the
  conclusion, shown only the conclusion + its cited basis rows) can answer **"does this follow from its
  cited basis?"** — that's *groundedness* (a fabrication check), and it's automatable. It **cannot** answer
  **"is this actually true about the real person?"** — a conclusion can perfectly follow from two cherry-picked
  rows and still be false/stale about the user. The truth arm's grader is the **human, or the agent
  explicitly acting as their delegated oracle**, never an LLM. Bind the ≥0.85 gate to the *truth* arm; the
  LLM-judge arm only gates fabrication (zero-tolerance).

- **n≈10-15 CANNOT power a Wilson-LB ≥ 0.85 — even a PERFECT score.** The gate is a *lower bound* precisely
  so a small lucky sample can't fake a pass. 11/11 → LB **0.74**; 10/11 → **0.62**; a perfect 41/41 → only
  **0.914**. To clear LB≥0.85 at a realistic ~5-8% defect rate you need **n≈80-100** graded items. So the
  certification workflow is: generate a LARGE sample (run the producer over many disjoint windows/inputs,
  dedup), grade it ALL, then compute the real LB. A "looks all true" read on a dozen items is a *premise
  signal*, not a passed gate — say so and go bigger rather than declaring victory on the small sample.

- **The dominant defect class is OVERCLAIM: a system-fact / one-off, relabeled as a user DECISION.** The
  misses that recur are not fabrications — they're attribution errors: the basis describes *how the system
  is built* ("the filter is baked in as a floor", "routing precedence is A->B->C") or a *one-off action*
  ("lock the DHCP reservation for THIS camera") and the model writes "the user has a standing decision that X."
  The groundedness judge passes it (it IS grounded), but it's false-about-the-user (a codebase fact, or a
  single task, wearing a "user decided" label). The fix is **prompt attribution discipline**, iterative:
  distinguish "the SYSTEM does X" from "ACE DECIDED X" (only the latter when the basis shows the user
  *choosing/preferring/directing/rejecting*, recurring across rows); a one-off proposed next-step is NOT a
  standing decision; a vague config detail ("uses specific JAR pools") is NOT a preference -> DROP it. This
  arc moved the defect rate **9.8% -> 7.3% -> 2.4%** across three prompt tightenings, same model — purely
  attribution-rule additions, not a model swap (same lesson as the oracle-fix trajectory above: the
  prompt/oracle was the bug, the model was capable the whole time).

- **GRADE HONESTLY AS THE DELEGATED ORACLE — do NOT fudge toward green.** When the user says "you grade
  them for me," you're the trust root; rounding a 0.836 strict-LB up to a pass is the exact fake-green the
  gate exists to kill. Grade conservatively (anything you can't verify against real ground truth = miss),
  show your work per-item, separate **verifiable-true** from **grounded-plausible-but-unverifiable** (count
  the latter as hits but DISCLOSE it — it's the seam that moves a 0.836 strict LB to a 0.916 lenient one),
  and report BOTH strict and lenient LB + the honest defect rate. Then make the floor call out loud:
  clear-0.85 / floor-0.80 / below-floor-tune-and-retry. Record the graded verdict as an artifact
  (`CERT_RECORD.json`). (The user grading a small sample MORE generously than your strict grade is the right
  direction for a trust check — hold the strict line for the formal gate.)

- **Deliver the grading sheet ENRICHED for the human.** Each item needs its *basis excerpts* (the source
  rows it was derived from) so the grader checks the *reasoning*, not just the claim, plus kind + confidence.
  doc-share it as a dark-mode HTML link (`--force` past the privacy scan for internal LAN-IP-only content) —
  the user reads conclusions about themselves more easily that way than from a JSON dump.

## Scope guard
Keep these gates "add an eval fixture + harness + test" — repo-only, no production
surface, no re-tuning the scorer (that's a separate change behind its own gate), no
Hard-Config / prompt / cron edits. Acceptance criteria must list each NEW invariant
(gate-pin, schema-exemption, the full mutation matrix, the baseline-fairness gate,
the non-author cert) — a stale AC list that still references the old single-mutation
framing is the partial-edit trap the review pass reliably catches in the final pass.

<!--
PROVENANCE: Material folded into `humanizer` from conorbronsdon/avoid-ai-writing.
  Source repo: https://github.com/conorbronsdon/avoid-ai-writing
  Commit:      6e1369dad98e61b165928f3849f225e11855cdaf  (version 3.10.0)
  License:     MIT (compatible with humanizer's MIT base; attribution preserved)
  Folded:      2026-06-23 by the orchestrator agent, via skill-hygiene master-check (same-job pair → fold, don't dup).
  Re-pull:     git clone --depth 1 https://github.com/conorbronsdon/avoid-ai-writing /tmp/aaw && diff against this file.
  What was DROPPED on purpose (not folded): the 1,661-line JS detector engine (detector/patterns.js),
    the .claude-plugin marketplace plumbing, CI sync scripts, and the candidate's voice-profile list
    (humanizer's "PERSONALITY AND SOUL" section is richer). We mine the doctrine, not the package.
  What this ADDS over humanizer's base 29 patterns: the epistemic guard ("signals, not proof"),
    tiered vocabulary (false-positive reduction), detect/edit modes, severity triage (P0/P1/P2),
    context profiles, and ~15 newer pattern categories (crypto/web3/social boilerplate the
    Wikipedia-derived list predates).
-->

# avoid-ai-writing — folded reference

The base `humanizer` SKILL.md (29 Wikipedia-derived patterns + the "add soul" voice work) is the
spine. This reference adds the material folded in from `conorbronsdon/avoid-ai-writing` that the base
lacked. Load it when you want the tiered word tables, the detect/edit modes, severity triage, or the
newer (post-2023, crypto/web3/social) pattern categories.

---

## 0. The epistemic guard — "signals, not proof" (READ THIS FIRST when assessing someone else's text)

This is the single most important addition, and it is **spine-level doctrine** (also summarized in the
main SKILL.md). The patterns below are statistically more common in LLM output, but **humans produce
the same shapes** — especially under deadline, in unfamiliar genres, or writing in a second language.

- Commercial AI detectors show false-positive rates **above 60% on non-native English writers**
  (Liang et al., Stanford, *Patterns*, 2023).
- Open-source detectors show overall misclassification **above 70%** (Jabarian & Imas, BFI Working
  Paper 2025-116, 2025).
- Adversarial paraphrase drops detection accuracy by **~88%** across every method tested
  (arXiv:2506.07001, 2025).

**Rule:** these are a useful *signal* — for cleaning up your own writing, and for a gut-check on whether
a piece reads as AI-generated. **Never make them the sole basis for a consequential decision** (academic
integrity, hiring, publication, attribution). Several rules here also fire on second-language writing,
deadline-pressed humans, and technical genres that compress vocabulary by design. Pair the signal with
context: who wrote it, what genre, what the writer's normal voice looks like, what other evidence exists.
**Signals, not proof. Worth acting on; not worth ruining someone's day over.**

---

## 1. Three modes

The base skill is rewrite-first. These two extra modes are worth having:

- **`rewrite`** (default) — flag AI-isms and rewrite. (This is humanizer's base behavior.)
- **`detect`** — flag only, no rewriting. Use when: the writer wants to decide what to fix themselves;
  the flagged patterns might be *intentional* (AI patterns aren't always bad in small doses); you're
  auditing text you don't want altered (published content, someone else's writing, reference material);
  or you want a quick scan. Output: the audit + an assessment of which flags are clear problems vs.
  judgment calls — **no rewrite**.
- **`edit`** — edit a file in place with minimal, targeted changes (change the flagged spans, not the
  whole document). Preserve passages that are already human. **Don't edit quoted material, code blocks,
  or text attributed to someone else** — flag those instead. For a large file, confirm which section to
  clean first. After editing, re-read and confirm the patterns are resolved; report what changed.

Trigger `detect` on "detect / flag only / audit only / just flag / scan / what AI patterns are in this."
Trigger `edit` when the user names a file and wants it fixed in place. Default to `rewrite`.

**Iterate to convergence (optional, cap N=2).** Rewrite mode already runs one corrective second pass.
When asked to "iterate / keep going until it's clean," repeat audit→rewrite until no patterns remain or
2 passes are reached — a third pass costs a full regeneration and rarely finds more. Report passes taken.

---

## 2. Tiered vocabulary (the false-positive-reduction mechanism)

The base skill has a flat word list. This tiered approach (adapted in the source from
brandonwise/humanizer) reduces false positives on words that are fine alone but suspicious in clusters.
**Match inflected forms** (adverb `-ly`, gerund `-ing`, plural, comparative, conjugations) unless a
variant carries a distinct honest meaning (e.g. `real` = factual vs. the "a real improvement" intensifier).

### Tier 1 — always replace (5–20× more common in AI text)

| Replace | With |
|---|---|
| delve / delve into | explore, dig into, look at |
| landscape (metaphor) | field, space, industry, world |
| tapestry | (describe the actual complexity) |
| realm | area, field, domain |
| paradigm | model, approach, framework |
| embark | start, begin |
| beacon | (rewrite entirely) |
| testament to | shows, proves, demonstrates |
| robust | strong, reliable, solid |
| comprehensive | thorough, complete, full |
| cutting-edge | latest, newest, advanced |
| leverage (verb) | use |
| pivotal | important, key, critical |
| underscores | highlights, shows |
| meticulous / meticulously | careful, detailed, precise |
| seamless / seamlessly | smooth, easy, without friction |
| game-changer / game-changing | describe what specifically changed and why it matters |
| hit differently / hits different | (say what specifically changed, or cut) |
| utilize | use |
| watershed moment | turning point, shift (or describe what changed) |
| marking a pivotal moment | (state what happened) |
| the future looks bright | (cut — say something specific or nothing) |
| only time will tell | (cut — say something specific or nothing) |
| nestled | is located, sits, is in |
| vibrant | (describe what makes it active, or cut) |
| thriving | growing, active (or cite a number) |
| despite challenges… continues to thrive | (name the challenge and the response, or cut) |
| showcasing | showing, demonstrating (or cut the clause) |
| deep dive / dive into | look at, examine, explore |
| unpack / unpacking | explain, break down, walk through |
| bustling | busy, active (or cite what makes it busy) |
| intricate / intricacies | complex, detailed (or name the specific complexity) |
| complexities | (name the actual complexities, or use "problems" / "details") |
| ever-evolving | changing, growing (or describe how) |
| enduring | lasting, long-running (or cite how long) |
| daunting | hard, difficult, challenging |
| holistic / holistically | complete, full, whole (or describe what's included) |
| actionable | practical, useful, concrete |
| impactful | effective, significant (or describe the impact) |
| learnings | lessons, findings, takeaways |
| thought leader / thought leadership | expert, authority (or describe their actual contribution) |
| best practices | what works, proven methods, standard approach |
| at its core | (cut — just state the thing) |
| synergy / synergies | (describe the actual combined effect) |
| interplay | relationship, connection, interaction |
| in order to | to |
| due to the fact that | because |
| serves as | is |
| features (verb) | has, includes |
| boasts | has |
| presents (inflated) | is, shows, gives |
| commence | start, begin |
| ascertain | find out, determine, learn |
| endeavor | effort, attempt, try |
| keen (as intensifier) | interested, eager (or cut — just state the interest) |
| genuinely / genuine (as intensifier) | (cut — just state the fact) |
| symphony (metaphor) | (describe the actual coordination or combination) |
| embrace (metaphor) | adopt, accept, use, switch to |

### Tier 2 — flag when 2+ appear in the same paragraph (legitimate alone, AI signal together)

| Replace | With |
|---|---|
| harness | use, take advantage of |
| navigate / navigating | work through, handle, deal with |
| foster | encourage, support, build |
| elevate | improve, raise, strengthen |
| unleash | release, enable, unlock |
| streamline | simplify, speed up |
| empower | enable, let, allow |
| bolster | support, strengthen, back up |
| spearhead | lead, drive, run |
| resonate / resonates with | connect with, appeal to, matter to |
| revolutionize | change, transform, reshape (or describe what changed) |
| facilitate / facilitates | enable, help, allow, run |
| underpin | support, form the basis of |
| nuanced | specific, subtle, detailed (or name the actual nuance) |
| crucial | important, key, necessary |
| multifaceted | (describe the actual facets, or cut) |
| ecosystem (metaphor) | system, community, network, market |
| myriad | many, numerous (or give a number) |
| plethora | many, a lot of (or give a number) |
| encompass | include, cover, span |
| catalyze | start, trigger, accelerate |
| reimagine | rethink, redesign, rebuild |
| galvanize | motivate, rally, push |
| augment | add to, expand, supplement |
| cultivate | build, develop, grow |
| illuminate | clarify, explain, show |
| elucidate | explain, clarify, spell out |
| juxtapose | compare, contrast, set side by side |
| paradigm-shifting | (describe what actually shifted) |
| transformative / transformation | (describe what changed and how) |
| cornerstone | foundation, basis, key part |
| paramount | most important, top priority |
| poised (to) | ready, set, about to |
| burgeoning | growing, emerging (or cite a number) |
| nascent | new, early-stage, emerging |
| quintessential | typical, classic, defining |
| overarching | main, central, broad |
| underpinning / underpinnings | basis, foundation, what supports |

### Tier 3 — flag only at high density (~3%+ of words; normal words AI overuses)

`significant/significantly` · `innovative/innovation` · `effective/effectively` · `dynamic/dynamics` ·
`scalable/scalability` · `compelling` · `unprecedented` · `exceptional/exceptionally` ·
`remarkable/remarkably` · `sophisticated` · `instrumental` · `world-class / state-of-the-art /
best-in-class`. Fix = replace some with specifics (numbers, comparisons, named precedent, the actual
forces), not all of them.

### Tier 3 phrases — flag at 2+ same-phrase uses OR 3+ distinct phrases in one piece

Multi-word boilerplate that stacks heavily in crypto/web3/DePIN/AI-infra content: `emerging
sector/space/category` · `the integration of (X with Y)` · `the intersection of (X and Y)` ·
`community-driven` · `long-term sustainability` · `user engagement` · `decentralized compute` ·
`(sustainable) reward emissions` · `tokenized incentive structures` · `designed for long-term [X]`.
Fix = name the specific thing/mechanism/horizon instead of the category label.

---

## 3. Newer pattern categories (beyond humanizer's base 29)

These post-date the Wikipedia "Signs of AI writing" list humanizer is built on — mostly social,
crypto/web3, and reasoning-model tells:

- **Generic future-narrative closers** — `modal (may/could/will/is poised to) + "become" + one of the
  most [adj] + (narrative/story/trend/theme/chapter/movement/force)`. Grammatically a prediction,
  zero testable content. Fix: make it falsifiable or cut. ("DePIN compute may exceed AWS spot pricing
  for embarrassingly parallel workloads by 2027" — yes. "…may become one of the most important
  narratives of the next cycle" — no.)
- **Hedge-stacked predictions** — `could potentially create`, `may eventually unlock`, `might
  ultimately transform`. Either word alone is fine; the stack cancels itself into confident nothing.
  Pick one.
- **"Real/actual" adjective inflation** — `real on-chain tokenomics`, `genuine utility`, `true
  product-market fit`: an empty intensifier on an abstract noun implying the rest of the field is fake
  without saying how. **Carve-out:** keep it when the contrast is *named* ("real on-chain settlement,
  not bridged IOUs"). The tell is the *unsaid* contrast.
- **Hashtag stuffing** — 6+ hashtags on a short post (hard flag; 5+ is a soft tell on `linkedin` /
  `investor-email`). LLM social posts default to 10–15; engagement plateaus past 3–5. Fix: 2–3 specific
  tags or none.
- **Bullet lists of bare noun phrases** — 5+ consecutive ≤6-word adj+noun items with no verb ("Stable
  mining efficiency / Reliable pool connectivity / …"). The tell is the *symmetry*. Fix: convert to
  prose or rewrite as checkable claims. Does NOT apply to genuine list content (changelogs, params,
  ingredients).
- **Reasoning-chain artifacts** — leaked thinking-model scaffolding in final output.
- **Confidence-calibration / self-labeling significance** — "Importantly," "It's crucial to
  understand," text announcing its own importance.
- **Acknowledgment loops & sycophantic tone** — "You're absolutely right!", "Great question!", endless
  validation. (Overlaps humanizer's base #20/#22 but worth the explicit category.)
- **Unfilled placeholders / chatbot citation-markup leaks / AI-tool URL `utm_source` params** — paste
  artifacts: `[INSERT X]`, citation-token markup, `?utm_source=chatgpt.com` query strings.
- **Novelty inflation** — "revolutionary," "first-ever," "never before seen" on routine work.
- **Smart-punct signature** — curly quotes co-occurring with em-dash + Oxford comma + clean typing
  (≥80 words) as a *weak corroborating* paste-from-chat signal. Never conclusive alone (Word/Docs/macOS
  auto-curl). Don't flag curly apostrophes on their own.

---

## 4. Writer-side diagnostic tests (not regex — judgment calls)

- **Paragraph-reshuffle immunity** — can you swap two body paragraphs without breaking the piece? If
  order doesn't matter, you wrote a list of points, not an argument that builds. Fix is structural:
  establish a through-line where each paragraph depends on the last.
- **Treadmill effect / low information density** — for each paragraph ask "what's actually new here?"
  If you could cut 40–60% and lose no information, the prose is restating the premise in fresh words.
  Fix: name the one fact/claim/turn each paragraph contributes; if there isn't one, cut it.
- **Vocabulary diversity (TTR)** — in 200+ word pieces, human prose lands ~0.50–0.65 type-token ratio;
  AI trends flatter, sometimes <0.40 on a vocabulary loop. NOT proof alone (narrow topics, technical
  reference, L2 writing legitimately compress). Fix: broaden the *what* (concrete instances), don't
  thesaurus it.
- **When to rewrite from scratch vs. patch** — if 5+ vocab hits across multiple categories + 3+ distinct
  pattern categories + uniform sentence/paragraph length, patching won't save it. State the core point
  in one sentence and rebuild.

---

## 5. Severity triage (P0 / P1 / P2) — for quick passes on large docs

- **P0 — credibility killers (fix immediately):** cutoff disclaimers ("As of my last update"); chatbot
  artifacts ("I hope this helps!"); vague attributions without sources ("Experts believe"); significance
  inflation on routine events; hashtag stuffing on `linkedin`/`investor-email`.
- **P1 — obvious AI smell (fix before publishing):** word-list violations (delve, leverage, robust…);
  template/slot-fill phrases; "Let's" openers; synonym cycling; formulaic openings; bold overuse; em-dash
  >1 per 1,000 words; generic future-narrative closers; social endorsement closers; hedge-stacked
  predictions; real/actual inflation; bare-noun bullet lists; Tier-3 phrase clustering (≥3 distinct).
- **P2 — stylistic polish (fix when time allows):** generic conclusions; compulsive rule of three;
  uniform paragraph length; copula avoidance; transition phrases (Moreover/Furthermore/Additionally);
  hashtag stuffing on `blog`/`technical-blog`; Tier-3 phrase repetition (single phrase ≥2×).

Quick pass = P0+P1. Full audit = all three.

---

## 6. Context profiles (adjust rule strictness by genre)

Pass an optional context hint, or auto-detect (short + hashtags = social; code blocks = technical;
salutation = email; default = blog): `linkedin` · `blog` · `technical-blog` · `investor-email` · `docs`
· `casual`. The big lever is hashtag/em-dash/bold strictness (tighter on professional surfaces, looser
where a launch post or a fragment-heavy social style is legitimate).

---

## 7. Self-reference escape hatch

When writing *about* AI patterns (a blog post, a tutorial, this skill's own docs), quoted examples are
**exempt** from flagging. Text in quotation marks, code blocks, or explicitly marked illustrative ("for
example, AI might write…") is not rewritten — only the author's own prose is.

---

## Attribution

Folded from [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
(MIT, v3.10.0, commit 6e1369d), itself drawing vocabulary research from brandonwise/humanizer and
structure-test ideas from Aboudjem/humanizer-skill. The base `humanizer` skill remains ported from
[blader/humanizer](https://github.com/blader/humanizer) (MIT) / Wikipedia's "Signs of AI writing."

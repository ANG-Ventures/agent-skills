# Authoring LLM-generation prompts: a length target forces FILLER, not substance

A lesson for any code/prompt that asks an LLM to *generate prose* (a digest overview, a
report section, a summary, a changelog blurb) where the prompt sets a length. It bit on
2026-06-25 (siftly-ace brief overviews) and the user caught it.

## The failure: "make it longer" → the model pads to the number

The user said "make the landscape summaries ~4x longer." I encoded that literally in the
generation prompt: **"a labelled paragraph per theme, aim 3000–7000 chars, hard ceiling
7200."** The model dutifully hit the char target — by **repeating the same scaffolding
sentences once per theme** to fill space:

- "shows the same lane from a different angle" ×6 (once per theme)
- "rounds out the theme with another concrete artifact or claim" ×6
- "carried this tag with N salience" ×6 (leaking the internal aggregate's salience numbers)
- "the cleanest example in the cluster" ×6
- "giving the selection guard enough variety to avoid a single-author pile-up" ×6

Result: a 779-word / 5,976-char wall that *looked* substantive but was ~half meta-scaffolding
describing the selection process instead of telling the reader the news. The user: "why the
heck is it so much longer? ... this robotic [text]."

**Root cause:** an LLM optimizes to satisfy the *most concrete* instruction. A char/word
target is concrete; "be substantive" is not. When you demand length the model can't fill
with real signal, it fills with filler — and the easiest filler is restating the same idea
in different words across each section. **Length is an OUTPUT of having things to say, never
an INPUT to force.**

## The fixes (do these together)

1. **Cap, don't target.** Set an *upper bound* ("≤300 words / ≤1900 chars, a tight read"),
   never a floor or an "aim for N." Pair it with an explicit escape hatch: **"if you can't
   fill the budget with real signal, write half — a short honest version beats a padded one."**
   That removes the incentive to pad.
2. **Prefer bullets / one-liners over "a paragraph per X."** "A paragraph per theme" is an
   open invitation to pad each one to paragraph length. "One line per theme, real content or
   drop the theme" structurally caps the filler.
3. **Ban the specific filler phrases by name.** Generic "no boilerplate / no filler" is too
   weak — the model doesn't think its scaffolding *is* filler. List the actual offending
   phrases as a 🚫 hard rule ("NEVER write 'shows the same lane from a different angle',
   'rounds out the theme', 'carried this tag with N salience', …"), plus the *categories*
   ("do NOT mention salience numbers, tag counts, 'the cluster', or 'the selection guard' —
   describe the NEWS, not the selection process"). Naming the exact strings is what makes the
   constraint bite.
4. **"Every sentence carries a proper noun or a number and says something NEW."** A
   per-sentence substance test the model can self-check is stronger than a vibe like
   "be informative."
5. **Don't leak the pipeline's internals into user-facing prose.** The "salience N", "the
   cluster", "the selection guard" phrasing came from the deterministic aggregate the prompt
   fed the model — it parroted the scoring vocabulary back as if it were content. If you feed
   a model internal scoring metadata as *source*, explicitly tell it those are RAW SIGNAL to
   summarize FROM, never vocabulary to repeat.

## Belt-and-suspenders: a hard cap downstream of the model

Keep a deterministic length backstop *after* the model (here `inject_overview.py`'s
`MAX_CHARS`, graceful sentence-boundary truncation) so a model that ignores the word budget
can't post a wall. But the cap is insurance, not the fix — a cap chops the END off (losing
the theme bullets), so the *prompt* must be the primary control that keeps it short to begin
with. Set the cap a little above the prompt's stated word target, not at it.

## Testing a generation-prompt change: drive a REAL model, count + grep

A prompt rewrite is only proven by running a **real LLM** against **real input** and checking
the output, never by eyeballing the new prompt text:

- Drive the actual generation against today's real aggregate/input (the repo's own AI client,
  a cheap model is fine — a *weaker* model than production is a good stress test: if the weak
  model complies, the stronger production model will too).
- Assert two things mechanically: **(a) the length** (`len(out.split())` words, `len(out)`
  chars — is it in range?) and **(b) the banned phrases are GONE** (`grep`/`in` each forbidden
  string + the leaked-vocabulary terms → must be zero). Before/after on the same input:
  779 words → 199 words, banned phrases 6× each → 0, is a real proof; "the new prompt looks
  tighter" is not.
- This is the generation-prompt cousin of "a doc example of code-rendered output is a CLAIM —
  re-render it from the live producer." The producer here is an LLM; run it.

## The meta-lesson: a vague human ask needs a CONCRETE-BUT-BOUNDED encoding

"4x longer" was a directional hint, not a spec. Encoding a directional hint as a hard numeric
*floor* over-corrected. When the user gives a fuzzy magnitude ("longer", "richer", "more
detail"), encode it as **richer CONTENT requirements + an upper bound**, and confirm the
number with the user if it's load-bearing ("~300 words, or do you want ~400?"). The original
real ask was "make the theme bullets say something real instead of 'recurring today'" — a
*quality* ask that I misread as a *length* ask. When in doubt, ask which axis they mean.

# Two recurring misdiagnoses: the "failure count" trap and the "enriched-but-not-indexed" gap

Both bit a real session (2026-06, siftly-ace X-bookmark pipeline). Both were "obvious"
explanations that were wrong, and both were resolved by reading the code/data instead of
asserting from a summary number.

---

## 1. The "failure count" trap — a gap between attempted and succeeded is NOT necessarily failures

**Symptom shape:** a batch job reports `attempted=N succeeded=M`, M < N, and you reach for
a plausible failure story ("the missing 55 are expired/unreachable media").

**Why the plausible story is often wrong:** the "succeeded" counter may only increment on a
*positive result*, not on *absence of error*. In the session, OCR's loop was:

```ts
for (const item of mediaItems) {
  attempted++
  const result = await runLocalOcr({ url })   // NO per-item try/catch
  // ...persist...
  if (result.text) succeeded++                 // only ticks when text was found
}
```

Two facts fall straight out of *reading the loop*:

- **There is no per-item `try/catch`.** So if any image had genuinely failed to fetch
  (404 / timeout / oversized), `runLocalOcr` would have **thrown and aborted the entire
  run**. The run completed with all N attempted → therefore **zero items errored**.
- **`succeeded` only ticks `if (result.text)`.** So the N−M "failures" are items where the
  tool ran fine and found *nothing to report* — textless images (faces, scenery, logos,
  abstract art), not fetch failures.

**The check that settles it (cheap, do it before asserting):**
1. Read the loop — does the "success" counter mean "no error" or "non-empty result"? Is
   there per-item error handling at all? (No catch + run completed = nothing errored.)
2. Pull a few of the actual gap items from the DB and inspect them.
3. Probe one live (e.g. `curl -so /dev/null -w "%{http_code} %{size_download}"`). A 200 with
   real bytes kills the "expired/unreachable" theory outright.

**The rule:** *a count is not a diagnosis.* Before attributing a gap between two counters to
a failure cause, confirm (a) what each counter actually increments on, and (b) what the gap
items actually are. Re-running "failed" items that aren't failures wastes spend/compute and
produces the identical empty result (deterministic tools give deterministic output on the
same input).

**The forward-looking follow-up (not a re-run):** textless items are the real candidates for
a *different* capability (image captioning / describe-the-image), not a retry of the same
tool. Distinguish "retry the failed job" from "this is a different enrichment tier."

---

## 2. "Enriched-but-not-indexed" — data lands in one search leg but silently not the other

**Symptom shape:** you generate rich derived text (OCR text, vision captions, video
transcripts) and assume it's searchable. It shows up in *keyword/FTS* search but a *semantic*
query never finds it — or vice versa.

**Root cause in the session:** a hybrid-search system has **two independent text-assembly
paths** that must each be fed:
- the **FTS/keyword indexer** (concatenated the raw media tags → worked), and
- the **embedding-input builder** (`buildEmbeddingInput`) which only assembled
  `tweet text + semantic_tags + entities` — it **never included the media text**.

So OCR text and 560 video transcripts were in FTS but **not in the vector index**. A new
caption tier would have hit the exact same wall.

**Why it hides:** each leg "works" in isolation; nothing errors. The enrichment writes
succeed, the embed run succeeds, search returns *something*. Only a query whose *only* match
is in the media text exposes the gap.

**The check:** when you add a new enrichment field, **trace it to every consumer**, not just
the one you were thinking about. Grep for where the field is read:
- keyword/FTS text builder,
- embedding-input builder,
- export/render (Obsidian note body),
- categorizer/ranker.
A field that's written but read by only a subset of those is a silent half-wired feature.

**Proof it's fixed (behavioral, not "the code looks right"):** run a query whose match can
*only* come from the new field — e.g. search a visual concept and confirm a tweet whose own
text is one unrelated word ("Evergreen.") surfaces purely via its image caption. If the
text-only baseline couldn't have matched, a hit proves the new field reached the index.

**Class invariant:** in any system with N parallel representations of the same content
(FTS + vector + export + rank), adding content to one is not adding it to the others. The
default assumption must be "I wired one leg"; verify the rest explicitly.

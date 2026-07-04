# Derived/summary surfaces must rank by the SAME authority as the gate — don't build a parallel ranker

## The pitfall (two ranking authorities that silently diverge)

When a system has an **authoritative gate** that decides which items count — a scorer, a selector, a
filter, a permission check, a ranking engine — any *secondary* surface that **summarizes, previews, or
aggregates the same pool** must derive its ordering/inclusion from that **same authority**, not from a
cheaper parallel computation. If it ranks by a proxy (the raw upstream label, a stale cached score, a
re-implemented heuristic), the two will agree *most* of the time and **disagree exactly when it matters**
— when the cheap signal is wrong but the authoritative gate already corrected for it. The bug is invisible
in normal cases and only surfaces as "the summary shows junk the real thing rejected."

This is a class of bug, not a one-off: a dashboard that counts rows differently from the query that gates
them; a preview that orders by `created_at` while the live list orders by a computed rank; a "top N"
widget that reads a raw model label while the production path applies a correction layer on top of it.

## Concrete catch (siftly-ace overview, 2026-06-29)

Two briefs gate posted items through a deterministic engine: `score_digest.score_item` applies a
"Backstop-4" junk-demotion + an off-topic guard on top of the model's raw labels, so crypto/scam/`$ticker`
posts the model mislabeled `core` get demoted out of the ranked list. But the **overview/"Landscape"
synthesis** read a *separate* aggregator (`overview_digest.py`) that ranked/filtered by the **model's raw
label** + the dump's cached `final_score` — it never applied Backstop-4. Result: junk the brief demoted
in its Top Stories still floated to the top of the overview. The overview could (and did) disagree with
the brief about what's worth showing.

**Fix shape (re-score through the one authority):** the aggregator now re-scores **every** pool item
through the *same* `score_item` call the gate uses, stamps the real deterministic score + an `excluded`
flag (junk OR off-topic), and ranks/filters by those — so the summary can never surface what the gate
itself rejects. Fail-safe: if the authority can't be imported/run, fall back to the cached values
(degraded but still renders), and expose a flag saying which path ran.

## The rule

- **Single source of truth for ranking/inclusion.** A summary of a gated pool calls the gate's own
  scoring/selection function; it does not re-derive a parallel ordering. Import and call the real thing.
- **The tell at design/review time:** you find two code paths that both decide "what's important here"
  from the same data — one in the production/gate path, one in a preview/summary/export path. That's the
  smell. Collapse them onto one authority.
- **The tell at runtime:** "the summary/preview/dashboard shows something the real list dropped" (or vice
  versa). That's almost always a parallel-ranker divergence, not a data bug.
- **Make divergence impossible, not just unlikely.** Re-scoring through the shared function (even if it
  costs a recompute) is correct; "copy the correction logic into the summary too" re-creates the drift on
  the next change to either copy.
- **Keep it fail-safe.** Re-scoring through the heavy authority can fail (import error, missing dep); fall
  back to the cached/raw values and surface a flag, so a summary degrades rather than breaks — but the
  *happy path* is the shared authority, not the proxy.

This is the data-flow corollary of the house "one source of truth" rule: a correction applied at the gate
is only trustworthy if every surface that shows the gated result is *downstream of that same correction*.

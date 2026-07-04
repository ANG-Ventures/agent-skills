# A "WONTFIX / terminal / unrecoverable" verdict is a HYPOTHESIS — ground-truth it before you ship it

**Class of trap:** when you close out work, the *easy* dispositions are "this is terminal,"
"the data is gone," "can't be recovered without X," "WONTFIX." They feel like honest
floors ("missing beats wrong"). But each is a **claim about the world** that you usually
made *without checking* — and a probing user will overturn it. A WONTFIX you didn't
ground-truth is the close-out twin of a fix you didn't verify: a confident assertion
standing in for evidence.

Real session (the orchestrator agent, 2026-06-21, fleet_shop Instacart residual recovery). I closed v0.2
with three WONTFIX/BACKLOG items. The user pushed on all three. **Two of the three were
wrong:**

| My verdict | What ground-truth showed |
|---|---|
| "12 flagged orders are terminal — reconcile-fails / dead data" | Re-analyzing the saved capture surfaced **two real transform bugs**; 9 of 12 recovered (12→3 open). |
| "product_id retro-fill impossible — old captures are gone" | The full prior capture (`ic_p3_raw.jsonl`, 98% product_id) was **still on disk**. Filled 1821 lines (0→84.9%). |
| "live re-walk is BACKLOG / too risky" | Ran it; **0 CAPTCHA, exit 0**, proved the self-heal loop end-to-end (the 3 it covered genuinely were terminal). |

The only item that survived was the one where I'd *actually measured* the data and shown
the price was mathematically unknowable (a quantity-discount the cached strings don't
expose). That's the tell: **a terminal verdict is only honest when it's backed by a
measurement, not by an assumption about what's possible.**

## The cheap checks that overturn a false "terminal" — run them BEFORE writing WONTFIX

1. **"The data is gone" → check disk first.** Saved captures, dumps, prior-run artifacts,
   `/tmp` outputs, backup files. The thing you think you'd have to re-fetch (re-walk,
   re-scrape, re-download — the expensive/risky action) is often already sitting in a file
   from an earlier run. `find`/`ls` the obvious locations before asserting it's
   unrecoverable. (Here: a 999K JSONL from the prior pricewalk had everything.)
2. **"It's a terminal/unfixable failure" → re-derive the root cause on the real records.**
   Don't accept the *flag's reason string* as the diagnosis. Pull the actual failing
   records and instrument them (Phase 1). A bucket of "reconcile_fail" or "no_match" can be
   N distinct, *fixable* root causes hiding under one label — here, two systematic
   price-string bugs (per-unit-cached-as-total; weight-string-mislabeled-each) plus
   stale-but-already-correct flags. "It didn't reconcile" is a symptom, not a terminal
   state.
3. **"Too risky / BACKLOG" → scope the actual blast radius, then do the small safe version.**
   "Highest-risk action" was true in the abstract, but the concrete task was 3 orders,
   paced, with an existing CAPTCHA-aware/resumable driver. Risk you *named* ≠ risk you
   *measured*. Often the honest move is to run the small, reversible slice and see, not
   defer the whole class.
4. **Distinguish "I measured it and it's genuinely impossible" from "I assumed it's
   impossible."** Only the former is a real WONTFIX. State the measurement in the closeout
   ("Σ overshoots subtotal by $13.98; the per-line split is unknowable from the captured
   data") — if you can't write that sentence with a number in it, you haven't earned the
   WONTFIX yet.

## The meta-rule

When you're about to write "terminal / WONTFIX / can't / gone / impossible / BACKLOG" in a
closeout, treat it exactly like a fix you're about to call "done": **it requires evidence,
not confidence.** Spend the 5 minutes to (a) check disk, (b) instrument the real records,
(c) scope the real risk. The reconcile gate / "missing beats wrong" doctrine protects you
either way — a recovery attempt that doesn't reconcile just stays flagged, so the *downside
of trying* is near zero and the *downside of a false WONTFIX* is leaving real, recoverable
value (here: ~75% of the residual + a whole rename-proofing column) on the floor. And the
user WILL probe it — arriving with the ground-truth already done beats being corrected.

See also: `read-prior-investigation-before-fixing.md` (a fix can be MEASURED→DECLINED — the
*valid* version of this, where the decline is backed by a measurement) and
`stale-count-and-current-state-attribution.md` (logs/counts prove what happened, not what's
true now — ground-truth current state before attributing or concluding).

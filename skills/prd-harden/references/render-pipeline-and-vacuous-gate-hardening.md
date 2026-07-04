# Hardening a render/transform pipeline + the vacuous-integrity-gate hole

When the artifact is a **rendered document** (HTML report, generated page, export) whose quality
depends on a multi-stage transform (resolve → render → post-process → publish), two bug classes bite
that a green unit suite over the *seam functions* completely misses. Both were caught live building
the youtube-notebooklm anchored-citation render (2026-06-13).

## 1. The "feature shipped but no LIVE render ever exercised it" gap

The anchored-citation code was committed, unit-tested at the seam level, and a **synthetic 17-source
fixture** was screenshotted as "proof." But the real user-facing report (153 sources) had been
rendered *before* the feature committed, so the live artifact shipped **without the feature** — and
nobody noticed until the user opened the page and asked "where is it?".

- **Rule:** a seam-level unit test + a synthetic-fixture screenshot is NOT proof the feature is in the
  shipped artifact. The closeout/harden evidence MUST be the feature observed on the **real,
  user-facing output** — the actual report, the actual page, regenerated *after* the code landed.
  "The function works on a toy input" and "the thing the user opens has the behavior" are different
  claims; only the second closes the item.
- **Cheap proof without re-running the expensive upstream:** if the pipeline persists an intermediate
  (`summary.json`, a manifest, the prior render's source data), add an **offline re-render harness**
  that replays the real data through the real render path **network-free** (no LLM re-query, no
  re-download). It produces the genuine artifact in seconds and is safe to re-run. (Here:
  `scripts/reanchor_v4.py` replayed the real 153-source report through the real
  render→anchor→integrity path with `resolve_videos=False`.) Ship this harness alongside the feature —
  it's both the proof tool and the future regression-render tool.
- **The missing test layer is the e2e through the top-level entry point.** Seam units prove each
  stage; only a test that drives the real `generate()`/`render()`/top function with a faked *external*
  dependency (a scripted NotebookLM `ask`, a stub API) catches a wiring/ordering regression where the
  stages don't compose. Add one per regime/branch the entry point supports.

## 2. The vacuous integrity gate — passes trivially on the EMPTY case

The publish gate was `check_anchor_integrity(html)`: "every forward link resolves to a row id, every
backref resolves to a body id." It returned `ok:True` on a report with **zero anchors** — no links →
nothing dangles → green. So the un-anchored v4 report sailed through the gate that existed
specifically to catch un-anchored reports. **A "no X is broken" gate is satisfied by "there are no
X."**

- **Rule (same family as `certification-fixture-teeth.md` §2, but for a PRODUCTION artifact gate, not
  a cert harness):** any integrity/consistency gate phrased as "every A links to a valid B" needs a
  **presence floor** for the case where the artifact is *supposed* to contain A's. Encode the
  expectation: "if the document HAS the downstream structure (Sources rows / `id=cite-G{g}`), it MUST
  also have the upstream markers (`class="cref"` anchors) — else the render silently no-op'd." Return
  that as an explicit flag (`unanchored_sources: True → ok:False`) and wire it into the publish abort.
- **Keep the scope guard.** The presence floor must fire ONLY when the artifact should be populated.
  A legitimately empty case (a citation-free report → no Sources rows AND no anchors) must still PASS.
  Pair the "rows-but-no-anchors → FAIL" test with a "no-rows-no-anchors → still ok" test so a future
  over-broad tightening (demanding anchors on every report) also reds.
- **RED-prove it against the real incident shape:** take a known-good rendered artifact, strip the
  upstream markers while leaving the downstream structure (`re.sub` the `<a class="cref">` away, keep
  the `<li id="cite-G{g}">` rows), and assert the hardened gate now returns `ok:False`. That replays
  the exact production failure; if the gate stays green you haven't closed it.

## 3. The render-and-READ harness catches CONTENT-LOSS the unit suite + spec review miss

Distinct from §1 (feature absent from the artifact): here the feature was **present, unit-green, AND
spec-approved**, but the rendered output **silently dropped a data field**. Caught 2026-06-14 building
the cron-alert v4 redesign — a `_render_single` structured branch built the message from
`headline (title+status) + facts` only, **dropping the producer-owned body verbatim**. So
`🔴 Claude Usage · quota` shipped with the actual `Sub #1 at 90% of 5-hour window` line *deleted*.
155 green unit tests, a 3-pass Opus spec review, AND a live smoke all missed it; the bug surfaced the
instant a before/after harness **rendered the real output and a human read it**.

- **Rule: when the deliverable is a rendered string/artifact, the hardening pass MUST render the
  actual output for each real producer/branch and READ it — don't trust unit-green + spec-approved.**
  Build a tiny harness that calls the live render function with representative real-shaped rows for
  every producer (the structured one, the multi-line one, the recovery one, the escalation-channel
  one) and prints/screenshots the result. A field-drop, a doubled emoji, a dangling separator, a
  collapsed identity line — these are *visible in 5 seconds of reading* and *invisible to a green
  assertion suite that never compares the full output to a human expectation*. The before/after
  diff form is best: it makes the regression obvious and doubles as the user-facing review artifact.
- **The unit suite tests CODE-vs-FIXTURES, not output-vs-INTENT.** The single-path tests were green
  because they asserted on `lines[1]` being the facts footer — they had *encoded the body-dropping
  behavior as the expected contract*. A test that locks the wrong output is worse than no test. When
  the render harness shows the bug, suspect the existing assertions *encode* it; update them to the
  correct contract and add a regression lock that RED-proves against the data-loss.

## 4. The spec's own implementation-prose can CONTRADICT its acceptance criteria and re-arm the bug

The cron-alert PRD had **AC#6: "no rendered alert — single OR digest — drops the identity."** Correct.
But a later implementation-prose paragraph (§12.4) added a carve-out: *"this body-verbatim rule applies
ONLY to the digest line; the n=1 single still uses the headline+facts layout."* That carve-out
**directly contradicted AC#6**, and the build faithfully followed the *prose*, re-arming the exact
identity-loss bug the amendment existed to kill. Source-reasoning agreed with the buggy prose — only
rendering the output exposed the contradiction.

- **Rule: acceptance criteria and implementation prose must agree; when they diverge, the AC wins and
  the prose is a bug.** During harden/closeout, when a render bug traces back to spec text, check
  whether that text contradicts an AC — if so, the as-built fix should *amend the spec prose* (record
  it as an as-built amendment, e.g. PRD §12.11) so the contradiction can't mislead the next implementer.
- **A default-path change can silently promote a previously-narrow code path to load-bearing.** The
  single-render path was a minor branch until grouping was turned OFF by default, which made it *the
  default*. A guard/fix applied "to the main path" (the digest) but not the now-default path is a
  classic miss. When a config flag flips which branch is default, re-audit every invariant against the
  newly-default branch specifically.

## Why a green unit suite hid both

The seam functions (`render_backref_html`, `linkify_markers_html`, `render_sources_section`) all had
passing unit tests — they correctly transform their inputs. But (1) nothing drove the *composition*
end-to-end against the real entry point, and (2) the gate's own test only ever fed it
*already-anchored* HTML, so its empty-case behavior was never exercised. The fix is two tests and one
flag, not a rewrite: an e2e-through-`generate()` per branch + a vacuity test on the gate + a
presence-floor flag. Total diff was small; the blast radius it closed (a user-facing artifact silently
shipping without its headline feature) was large.

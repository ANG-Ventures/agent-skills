# Migrating a test suite when a behavior CONTRACT changes (not a bug fix)

When an approved spec deliberately changes a system's behavior contract, an existing test
suite will go red *en masse* — and that is the **expected, healthy** signal, not a regression
to "make green." The discipline is to migrate each red test to the NEW contract while
preserving its original *intent*, then add a dedicated suite for the new acceptance criteria.

Proven 2026-06-13/14 on the cron-observability v4 alert-delivery change (grouping-off default,
flush-on-write, suppression-window dedup): 23 existing tests went red, all asserting the OLD
contract. Migrating them + adding a 13-test v4 AC suite took the project 116→153 green, and the
NEW suite caught a real production bug the migration alone would have missed.

## First: triage red tests into two buckets — DON'T assume they're all the same

After a contract change, every red test is one of:

1. **Asserts the OLD contract (must be rewritten to the new reality).** The behavior it
   checked was intentionally changed. Rewrite the assertion to the new contract, keep the
   test's *purpose*. e.g. "enqueue leaves a `pending` row" → under flush-on-write the row is
   `sent` immediately; assert `status='sent'` + the send landed on the right target.
2. **Exercises a MECHANISM that legitimately needs the old precondition staged.** The test
   isn't about the changed behavior — it tests an orthogonal mechanism (a lock, a bounded
   flush, a dry-run, a prune) that needs rows in the pre-change state to run. These get a
   **test-only staging seam**, not a rewrite (below).

Get the FULL list first (`pytest --tb=line | grep -oE 'tests/.*\.py:[0-9]+: [A-Za-z]+' | sort -u`)
— the summary reporter may truncate to the first N. Classify all of them before editing one;
several will look identical (`TypeError: 'NoneType' object is not subscriptable` = querying a
row the new contract no longer leaves where the old test looked) but split across both buckets.

## The test-only staging seam (bucket 2)

When a behavior change makes the *default* path skip a state that mechanism-tests depend on,
add a **narrow, defaulted-to-production-behavior** parameter so tests can stage the old state
WITHOUT changing production. Do NOT make the production default the test-friendly value.

Example (flush-on-write): `enqueue(..., flush_on_write: bool = True)`. Production stays
immediate; mechanics tests pass `flush_on_write=False` to leave a `pending` row to inspect.
Document it in the function docstring as "set False ONLY in tests that need a staged row;
production always leaves it True." This keeps the lock/bounded/dry-run/prune/concurrency tests
testing their actual mechanism instead of being deleted or contorted.

The seam is for *orthogonal mechanism* tests. A test that checks the changed behavior itself
gets rewritten to the new contract (bucket 1) — never staged around.

Note: a standalone e2e SCRIPT (not a pytest, e.g. `tests/e2e_flush_lock.py` that races real
flush processes) that depends on staged `pending` rows uses the SAME seam — set
`flush_on_write=False` when populating its fixture rows. After a default flip, audit the
standalone dogfood/e2e scripts too; they don't show up in the pytest red count and a closeout
gate (`verify.sh`) will fail on them separately ("expected 40 pending, got 0").

## Write a DEDICATED acceptance-criteria suite for the new behavior — it finds real bugs

Migrating old tests proves you didn't *break* the old surface. It does NOT prove the new
behavior is *correct*. Write a fresh suite, one test per acceptance criterion in the spec
(`test_<feature>_behavior.py`), asserting the new contract directly. This is where real bugs
surface, because these tests exercise paths the migrated tests never did.

This session the AC suite caught a genuine production bug: the inline flush-on-write called
`flush(conn, sender=sender)` **without threading `now=`**, so the dedup suppression window was
measured from wall-clock instead of event time — invisible to every migrated test (they don't
inject time at a window boundary), but the AC test `test_repeat_past_window_sends_again` failed
because the boundary re-send didn't fire. One-line fix (`flush(conn, now=now, sender=sender)`),
found only because the dedicated suite injected `now` across the window edge.

AC tests to always include for a delivery/dedup/flag-gated change:
- **Each flag at its default** (grouping-off → N distinct rows = N standalone, asserted on the
  *sweeper/batch path* not just the single-enqueue path; storm-cap-off → full burst all deliver).
- **Each flag flipped on** restores the prior behavior (proves reversibility is real, not claimed).
- **The preserved return contract** — if the spec says "the `action` return value is unchanged,"
  assert every value (`queued`/`sent`/`suppressed`) still appears; surface the new outcome in a
  *separate* field so old `action ==` assertions stay valid.
- **The failure-mode safety property** — a thrown `sender` inside the immediate path must NOT
  fail the enqueue and the row must stay durable + swept later (commit-then-act, swallow-all).
- **The honest counter/×N truth** — if there's no message-edit path, the first delivery shows the
  count at send time and the accumulated ×N surfaces on the *next boundary send*, not retroactively.

## Test-construction traps that masquerade as code bugs

When an AC test fails, check the test before the code — two bit this session:
- **A pre-empting collapse hid the path under test.** A storm-cap test fed identical-key rows;
  the *dedup-collapse* (which runs before the cap) absorbed them all into one pending row, so the
  cap never counted enough to trip. The cap counts rows that actually accrue — use the real
  production path (each fires + window-suppresses, accreting countable rows) or vary the content,
  not the test's mental model.
- **Uniform/identical fixtures don't discriminate.** (cf. the average-skew trap in SKILL.md) — a
  fixture where every item is identical can pass both the broken and correct implementation. Make
  the fixture exercise the *distinguishing* case.

## Honest-read for the live e2e (cross-host delivery)

When the change ships to a remote host and the e2e is "a real alert lands in chat," DB-side proof
(`status='sent'`, target, `flushed_at` stamped) + the sender's success return is strong but is NOT
eyes-on. The bot's *own* token may 403 on channel reads (missing Read-History perm) — use the
agent's native chat-read tool (`discord fetch_messages`) to read the channel back and confirm the
real rendered bytes. The before/after is often visible right in the channel history (old raw-path
spam at one timestamp, new collapsed ×N at a later one) — that side-by-side IS the proof artifact.

## Cross-host source-of-truth sync (when the changed module lives on >1 host)

If the edited module exists on multiple hosts (a shared renderer/map), pick ONE as source of
truth, push, then `git pull --ff-only` on the consumers and assert byte-identical parity
(`md5(json.dumps(THE_MAP, sort_keys=True))` on both) rather than hand-editing two copies — two
hand-maintained copies of a vocabulary silently drift (see SKILL.md "second copy of a vocabulary").
Run the suite on the consumer host too (its venv, not system python) — "green on my host" ≠ "green
on theirs."

The consumer's interpreter often differs from the source host's. The verify gate's `python3` may be
old (py3.7) while the consumer has only a project `.venv` (py3.14) and a system `python3` with no
pytest. Find the interpreter that actually has pytest (`.venv/bin/python`, `python3.12`, …) and run
the suite with THAT — a "No module named pytest" is a wrong-interpreter signal, not a missing test.
Confirm the consumer's skip-list is pre-existing host-file-absence (a wrapper/script not deployed
there), never your new tests.

## The default-flip exposed a missed invariant path (the real bug this redesign produced)

The most important bug in the whole v4 redesign was NOT a test-migration issue — it was a
**correctness invariant missed on one render branch**, surfaced only when the before/after artifacts
were generated against the real renderer (2026-06-14, the turn after the migration).

- **The invariant:** "the producer-owned body is always preserved verbatim; the renderer frames, it
  never summarizes identity" (the C11 rule, born from the user catching "Phase7 Speed: STALE…" being
  gutted to "overdue/stale").
- **The miss:** C11 had been applied to `_format_digest` (the multi-finding path) but the
  *structured-single* path `_render_single` still built its message from headline + facts only,
  **dropping the body entirely**. This was latent-harmless while digest-mode was the default.
- **What made it a SHIPPING bug:** the v4 spec turned `GROUPING_ENABLED=False`, so the single became
  the **default** path — every structured producer (claude-usage, failover) would have gutted its own
  body in production.
- **How it was caught:** generating the "AFTER" before/after sample by calling the *real*
  `_render_single` showed `🔴 Claude Usage · quota` with the `Sub #1 at 90%…` line *missing*. The
  artifact was the instrument.
- **The fix + lock:** render body verbatim beneath the headline in the structured branch too (with
  echo-suppression when the sole body line just repeats the headline), plus a dedicated regression
  test per branch. Live-verified on the Linux GPU box the logs channel by reading the real rendered message back.

Two durable takeaways (both promoted to SKILL.md body):
1. An invariant fixed in one output path must be applied to ALL sibling paths — grep `def _render|def
   _format|def _emit` and lock each branch with its own test.
2. When a spec flips a default, re-audit every invariant against the newly-default path before shipping.

## The GOLDEN render-snapshot suite — institutionalizing "render it and look" (2026-06-15 follow-up)

A before/after artifact catches the regression once; it leaves no guard for the next change. The
durable closure of the C11 lesson was a frozen-snapshot suite (`tests/test_golden_render.py`, 9 tests).
This is the permanent version of "generating before/afters is a debugging instrument."

### Why the 155 green tests + Opus review missed it (the mechanism the golden fixes)
Every existing test asserted on PARTS of the render (`lines[1] == facts`, `lines[0] == headline`).
The buggy spec prose ("the n=1 single uses the facts-path headline+facts layout") and those
part-assertions AGREED with each other — both encoded the body-drop. A part-assertion can be
"correct" against a buggy contract. A **whole-output snapshot cannot agree with buggy prose** — it
only agrees with the literal bytes the renderer emits, so a body-drop shows up as a diff immediately.

### Construction recipe
1. **One row builder per output SHAPE**, not per field. The cron gallery: `bare_single`
   (unstructured legacy), `structured_single` (the DEFAULT path under grouping-off — the exact shape
   the bug gutted), `structured_multiline` (failover `down`, multi-line body), `recovery_single`
   (✅ headline), `telegram_escalation` (escalation channel, `-#` small-text stripped), `room_split_single`
   (`subsystem/room` → `Title · Room`). Add a shape only when a render BRANCH diverges.
2. **Freeze the complete final string verbatim** in a `GOLDEN = {name: (builder, expected)}` dict.
   Read top-to-bottom it IS what lands in chat. The assert prints expected-vs-got on drift with a
   "LOOK at the diff; if intentional, update GOLDEN['name']" message — the human is forced to see it.
3. **Kill the silent-skip trap with a renderer-filled placeholder.** The only env-dependent token in
   a render is the timestamp (PT on modern interpreters, UTC fallback where `zoneinfo` is absent —
   e.g. the verify gate's py3.7). Guarding with `if not has_pt_tz(): return` silently skips every
   byte-golden under the gate's interpreter — gutting the suite where it matters most. Instead freeze
   `"-# {ts}"` and fill it from the renderer's OWN stamp fn: `TS = Q._pt_stamp(NOW)` then
   `expected.format(ts=TS)`. Byte-exact on layout/body/footer on EVERY interpreter, zero skips; the
   "variable" part is produced exactly as production produces it.
4. **Add tz/env-independent invariant tests beside the byte goldens** so the core property holds even
   where a stamp would legitimately differ: `for name,(builder,_) in GOLDEN: assert each body line in
   render(builder())`; plus `"-#" not in telegram_render` / `"-#" in discord_render`.
5. **RED-prove teeth, restore byte-identical.** Break the multi-line continuation render → confirm
   `test_every_shape_preserves_body_verbatim` fails with the *exact dropped line* in the assertion →
   `cp` the backup back and `shasum` to prove byte-identity. A golden that passes with the code broken
   tests nothing.

### Calibration gotchas (first-run snapshot mismatches that are NOT bugs)
- A `title=` override SUPPRESSES subsystem/room resolution — to exercise `pipecat-hub/kitchen` →
  `Pipecat Hub · Kitchen` in the headline, the row must omit the title override (let the source resolve).
- Get the actual emoji from the real renderer before freezing (medium = 🟡, not ℹ️; high = 🔴; recovery
  = ✅). Run a 3-line `python3 -c "print(repr(Q._render_single(row, now=NOW)))"` to capture ground-truth
  output, then paste it into GOLDEN — don't hand-type the expected string (hand-typed = proves nothing).

Fold the suite into the verify gate so it runs every closeout. Sync to consumer hosts and run under
THEIR pytest interpreter (the gate-host python3 may lack pytest; use the project `.venv`).

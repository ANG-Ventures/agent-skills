# A feature silently degrades because a helper crashes on the LIVE data shape (not the test shape)

Companion to §5g ("a feature isn't rendering → grep the live log for its degrade reason") and the
test-fixture-diversity lesson. This captures a sharper, recurring class: **a "richer" output variant
renders only on ONE of its producing paths, and never on the dominant one, because the producer raises
on the data shape the dominant path actually feeds it — a shape the tests never exercised — and the
raise is swallowed by an `except → fall back to the simpler form`.** (Proven 2026-06-22, the in-turn
compaction-announce degrading to the single-line form for every real session.)

## The shape of the bug

You have a feature with two (or more) producing paths that converge on the same renderer:

- **Path A** (e.g. session-hygiene compaction) feeds the producer **flat-string** content (`{"role",
  "content": "..."}`), and the granular/rich form renders correctly. Your tests use this shape.
- **Path B** (e.g. the in-turn / threshold compaction) — usually the *dominant* path — feeds the
  producer the **live API shape**, where `content` is a **list of content blocks** (`tool_use` /
  `tool_result` / `text`), not a string. The producer's text-classifier (`regex.search(content)`,
  `content.startswith(...)`, `content.lower()`) **raises `TypeError` on the list**, the caller's
  `except Exception` catches it, sets `stats = None` (or the rich payload to None), and the renderer
  falls back to the simpler one-line form.

Result: the granular variant has been **dead on the dominant path since it shipped**, while looking
healthy on the path the tests cover. Nobody notices, because the simpler form is still a valid-looking
output and the failure is swallowed.

## Why it hides so well — three compounding masks

1. **The crash is swallowed by the feature's own resilience.** A `try: build_rich(); except: degrade`
   converts a hard `TypeError` into a quiet "simpler output." The exact silent-degrade pattern §5g warns
   about — but here the trigger isn't bad arithmetic, it's a **wrong input type**.
2. **The degrade reason logs at `debug`, not `warning`.** The hygiene path logged
   `COMPACTION_STATS_RECONCILE_FAILED` at WARNING (greppable, §5g works), but the in-turn path logged
   its build failure at `logger.debug(...)` — invisible in a normal INFO gateway log. So the §5g grep
   came back empty on the failing path even though it WAS degrading. **Corollary to §5g: if the grep for
   the degrade marker is empty but the feature is still degrading, the degrade log may be at `debug` —
   check the log LEVEL, and the fix should promote any swallowed-build failure to a greppable marker.**
3. **The tests are all green** because every fixture uses the simpler (flat-string) shape. A unit suite
   that only ever passes `{"role":"assistant","content":"text"}` verifies the producer for *that* shape
   and proves nothing about the list-content shape the live path sends. (Same family as the
   transform-fixture-diversity lesson in `instrument-before-guessing-when-model-is-symptom.md`, applied
   to a *producer* fed live API messages instead of a wrap/unwrap transform.)

## How to find it fast

1. **Reproduce the crash at the unit level with the LIVE shape, not the test shape.** Don't theorize
   from the reconcile math. Construct the input the dominant path actually feeds (here: messages whose
   `content` is a `list` of `{"type":"text"/"tool_use"/"tool_result", ...}` blocks) and call the
   producer directly. A `TypeError: expected string or bytes-like object, got 'list'` at the
   text-classifier line IS the root cause — one `execute_code` probe, no source spelunking.
2. **Confirm the two paths diverge by data shape.** Grep how each path builds its input. One will use a
   flat `{role, content:str}` projection (the working path); the other passes the raw API messages
   (the broken path). The classifier crashes only on the latter.
3. **Don't trust a green test suite as coverage** — grep the fixtures for the shape diversity. If every
   fixture's `content` is a `str` and the live path sends `list`, the suite is blind to the bug.

## The fix (two parts, both RED-proven)

1. **Make the shared text-classifier shape-robust by coercion, not by branching at each call site.**
   Add one helper that coerces any `content` (`str` / `list-of-blocks` / `dict` / `None`) to a
   searchable string (extract `text`/`input_text`/`output_text`/`content` from each block, join), and
   route the classifier through it so it can never raise on an exotic shape. The marker you're searching
   for lives in text, so text-extraction is the correct coercion.
2. **Make any role/type classification shape-aware too.** If the feature also buckets by `role ==
   "tool"` (the flat-hygiene shape), it will mis-bucket the live shape where a tool *result* is a
   `role="user"` message carrying a `tool_result` block and a tool *call* is a `role="assistant"`
   message with a `tool_use` block. Add an `_is_tool_message()` that recognizes BOTH (`role=="tool"`
   OR a `tool_result`/`tool_use`/`tool_call` content block) so the per-bucket breakdown renders on the
   live path, not just the test path.

RED-prove each: a unit test that feeds the live (list-content) shape must fail before the fix and pass
after; reverting either helper must fail its matching test. A reconciling/validating data structure's
`validate()` is unchanged by the fix — you're only fixing the input-shape crash that suppressed the
rich form.

## The verification trap — and how to prove it ORGANICALLY on real data

The cheap proof is "call the formatter with a synthetic stats object" — but per coding-guardrails, a
self-constructed fixture that round-trips proves the *format*, not that the *live system produces that
value on the real path*. For a feature gated behind a runtime trigger (a compaction threshold, a queue
depth, a size limit), prove it by **driving the real engine to the real terminal status on real data,
then rendering ITS output through the real done-site** — not by hand-feeding the formatter:

1. **Force the real trigger on a non-user-facing rig.** Use a test agent/profile (here: aegis, the LCM
   test rig, `MEM0_CAPTURE=off`) — back up its config, lower the *correct* threshold knob, restart.
   **Find the RIGHT knob:** the engine often has its OWN trigger separate from the generic one — e.g.
   LCM honors `context.context_threshold` (default 0.35 of the model window) + `fresh_tail_count`
   (default 32), NOT the `compression.threshold` you'd reach for first. Lowering the wrong one produces
   `should_compress=False` / `noop` forever and you chase a phantom. Read the engine's `should_compress`
   / fold logic to learn which knob actually gates the fold.
2. **Build real input via the real surface.** Drive a few CLI/gateway turns that run TOOLS (so the
   session carries genuine list-content `tool_use`/`tool_result` blocks — the exact shape that crashed),
   pushing past the engine's message/token fold point.
3. **Run the REAL engine to a REAL terminal status.** Reconstruct the live session from the store and
   call `engine.compress(messages, current_tokens=...)`; assert `_last_compression_status == "compacted"`
   (a genuine fold, NOT `noop`). A lifecycle banner ("Compacting context…") is NOT proof — it's the
   *attempt*; the done-site only fires on the terminal status. (`noop` is the engine correctly declining
   to fold a too-small context — size the input so it genuinely folds.)
4. **Render ITS real before/after through the real done-site** (`_emit_compaction_announce` →
   formatter → the delivery leg with a capturing `_emit_status`), and read the rendered line. That
   exercises the identical code the gateway runs — no mocks, no synthetic stats.
5. **Restore the rig's config from backup and restart clean; confirm 0 new errors.** A threshold/knob
   mutation is test-only state; revert it the moment the proof lands.

This is stronger than catching a banner scroll past in a live chat: the CLI/console surface may show
only the lifecycle banner (not the done-line), and forcing a *natural* trigger can need an impractically
huge session. Driving the engine to the terminal status and rendering its real output is the honest e2e.

## Deploy note for a live-import bug

When the broken code is imported by a long-running daemon (a gateway), the fix is staged-not-live until
the process restarts: the running process loaded the old bytecode at startup. Cherry-pick onto the live
tree, but the feature only renders correctly after the daemon reloads — and restarting the agent's OWN
gateway interrupts the live session (a gated action; surface it as the user's call). Verify the
post-restart process imports the fixed symbols (`pid` start-time vs file mtime; import the module and
check the new helpers exist) before claiming it's live.

## The class invariant

A feature with multiple producing paths that share a renderer is only as correct as its coverage of the
**data shape each path actually feeds**. A green test suite over the *simpler* shape, plus a healthy
render on the *easy* path, is NOT proof the *dominant* path works — its producer may be crashing on the
live shape and silently degrading. Reproduce with the live shape, fix the shared classifier by
coercion, and prove it by driving the real engine to its real terminal status on real data.

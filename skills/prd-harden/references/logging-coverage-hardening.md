# Logging / observability coverage — a hardening dimension

Folded into `prd-harden` (rule 13, 2026-06-28). Inspired by the Forward Future Loop Library's
"logging coverage loop" (add useful tested logs to every important path), grounded in this
fleet's redaction + alerting reality.

**Core reframe:** logging is not decoration you sprinkle at the end — it's *testable coverage*
of the failure surface you're hardening. A failure path you can't *see* fail in production
isn't hardened. The hardening pass that adds a failure test (rule 4) also owns making that
failure **legible when it fires live**. Source-line review alone misses gaps; you inspect the
*emitted event*.

## When this dimension applies (scale to blast radius)

Run it when the feature has any of: real failure paths, a cron/daemon/background job, a
service boundary, an integration seam, or a **silent-degrade branch** (try/except → fallback,
feature-flag default, graceful no-op). A pure stdlib helper with no failure surface does not
earn a logging pass — don't invent one.

## The procedure

### 1. Inventory the important paths
List every path worth tracing and, for each, define what it should emit:

| Field | What | Why |
|---|---|---|
| **event** | a stable name (`payment.capture.failed`, not an interpolated sentence) | greppable, aggregatable, survives copy reword |
| **outcome** | success / failure / degraded | so you can count failure rate, not just presence |
| **severity** | debug / info / warning / error | routes attention; failure paths are ≥ warning |
| **correlation** | request-id / run-id / job-id / session-key | ties a multi-step flow together across lines |
| **fields** | the structured context a debugger needs (ids, counts, the *reason*) | turns "it broke" into "it broke because X" |

Stable structured fields beat interpolated prose: `log.warning("degrade", reason=r, run=id)`
not `log.warning(f"had to degrade because {r} on run {id}")` — the former is greppable and
parseable; the latter rots and can't be aggregated.

### 2. Add structured logs to uncovered paths
- Cover the **failure and degrade** paths first (they're the ones nobody sees until 3am), then
  the boundaries. Don't add low-value happy-path noise or duplicate an event already emitted
  upstream.
- **Every silent-degrade branch logs a LOUD, greppable reason.** This is the single
  highest-value rule: the dark-feature trap (a feature that ships, passes tests, merges, and
  then *never fires* because a fallback quietly absorbs its failure) is only debuggable in 30
  seconds *if the degrade logged why*. A degrade that logs nothing guarantees the dark feature
  goes unnoticed. Pattern: `COMPACTION_STATS_RECONCILE_FAILED <reason>` — one line, a stable
  prefix, the reason. (See `prd-closeout` "silently dark in production" — that whole failure
  class is prevented by this one rule plus a success-marker grep.)

### 3. Test the logs — success AND failure outcomes
Logging coverage is *tested* coverage. For each important path, assert on the emitted event,
not the source line:
- **pytest:** `caplog` (assert a record with the expected event name + level + key field) or a
  capturing handler.
- **Node/TS:** spy on the logger / capture transport, assert the structured payload.
- Test the **failure** outcome explicitly: force the path to fail, assert it logs at the right
  severity with the reason field populated. A failure path that fails *silently* in the test
  is a failure path that will fail silently in prod.
- **Inspect a representative emitted record by eye** at least once — source review confirms a
  log *call* exists; reading the actual emitted line confirms it carries useful context and
  isn't `degrade reason=None`.

### 4. Redaction gate (NEVER log secrets/PII)
This is a trust-boundary, not a nicety. Never log credentials, tokens, API keys, session
secrets, or personal data.
- For this fleet, reuse the existing hygiene: the same token-shape scrubbing the daily-journal
  (`SECRET_RE`) and `notify` paths use, and `~/.hermes/scripts/brand-safe-write.py` where a
  redaction layer is in play. Don't invent a new redactor.
- **Test the redaction:** feed a path a token-shaped value and assert the emitted log does NOT
  contain it (RED-prove by removing the scrub → the test catches the leak). A redaction you
  haven't watched catch a planted secret is an assertion, not a guard.
- Watch structured fields, not just the message string — a `user` object spread into log
  fields can leak an email/token the message template never named.

### 5. Repeat until covered
Every important path has tested coverage OR a documented reason not to log (e.g. a tight inner
loop where logging would dominate cost — say so in a comment, don't silently skip).

## Pairs with the dark-feature grep (closeout)

Logging coverage is the *build-side* half; the *closeout-side* half is proving the primary path
actually fired in production — `grep -c "<success-event>" log` should be > 0 and ideally ≫ the
fallback-event count. A fallback-only log = the feature is dark. The degrade-reason log from §2
is what makes that grep diagnosable instead of just "huh, zero hits." See `prd-closeout` →
"A merged-green feature can be SILENTLY DARK in production."

## Anti-patterns

- **Logging the happy path, silent on failure.** Backwards — the failure path is the one you
  can't see and most need to.
- **Asserting the log *call* exists (source grep) instead of the *emitted event*.** A call
  with a `None`/empty reason field passes a source grep and tells you nothing at 3am.
- **Interpolated prose instead of stable event + fields.** Unaggregatable, rots on reword,
  and a renamed label silently breaks every dashboard/grep keyed on it.
- **A silent-degrade branch that logs nothing.** Undebuggable; the dark-feature factory.
- **Logging a secret/token/PII**, especially via a spread structured field. Test the redaction.
- **Adding noise to look thorough.** Duplicate events and low-value debug spam raise cost and
  bury the signal. Cover the *important* paths; logging coverage is risk-proportional like the
  rest of hardening.

# Verify a handed-off diagnosis against the raw logs before patching

**Class of trap:** you're given a root-cause writeup (by another agent, a teammate,
a past session, or your own earlier reasoning) plus an approved fix, and asked to
"just implement options 1 & 2." The diagnosis reads authoritative and the fix
sounds reasonable. **A handed-off diagnosis is a hypothesis, not a finding —
re-derive it from the primary evidence (logs/metrics) before you touch code.**
The cost of skipping this is shipping a tuning change against the wrong mechanism.

## Worked example (2026-06, Hermes Codex non-streaming hang)

the backup agent handed off a 3-part writeup: a 07:00 cron Codex turn hung, root cause =
"the fast-reconnect TTFB watchdog is wired to the *streaming* path only; the cron
ran *non-streaming* so it only had the blunt 90s stale timer." Approved fix:
(1) tighten the non-streaming Codex stale timer, (2) force streaming for cron
Codex turns. The task arrived as "Yes, try 1 and 2 and confirm with e2e testing."

Reading the actual source + `~/.hermes/logs/errors.log` corrected the mechanism:

- **TTFB is NOT streaming-only.** `agent/chat_completion_helpers.py:interruptible_api_call`
  (the *non-streaming* path) already has a no-byte TTFB watchdog. It just never
  fired because its default cutoff is **120s** while the stale timer is **90s** —
  the blunt timer always wins first. The real bug is *watchdog ordered behind a
  shorter timer*, not *no watchdog*.
- The TTFB-disable-above-25k-tokens rule (`HERMES_CODEX_TTFB_DISABLE_ABOVE_TOKENS`)
  was a red herring: the logged context was **~13.5k tokens**, below the threshold.
- The failure signal was `ReadError [Errno 32] Broken pipe` with three clean
  **90s** gaps (`07:02:03 → 07:03:36 → 07:05:12`), i.e. the stale timer firing —
  not the classic silent no-byte hang the writeup described.
- `conversation_loop.py` **already prefers streaming even without consumers**
  (`_use_streaming = True` unless `_disable_streaming` latched). So "force
  streaming for crons" is already mostly true; the real Option-2 fix is "don't let
  a transient stream error permanently latch a cron into non-streaming."

Net: both approved options still pointed roughly the right direction, but the
*implementation* changes once you know the true mechanism (cap TTFB to
`min(ttfb, stale-10s)` so it reconnects ~30-40s; the maintainers raised the
cutoff 12s→120s on purpose to avoid killing legit prefill — so "just make it
small" would re-introduce a documented prior regression).

## The procedure

1. **Find the primary evidence the writeup was derived from** — the actual log
   lines, metrics, or capture. Grep the timestamp window yourself
   (`grep '07:0' errors.log`). Do not trust the prose summary of what the logs say.
2. **Match the failure signal to the claimed mechanism.** Error type, timing gaps,
   token counts — do they actually fit the story? Three even 90s gaps = a 90s
   timer, not a 120s one. A `Broken pipe` ReadError ≠ a silent no-byte hang.
3. **Read the code paths the fix would touch** and check the writeup's premises
   against current source (the code may have moved on since the diagnosis was
   written — e.g. streaming may already be the default).
4. **Check for documented prior rationale** on any value/threshold you'd change.
   A comment like "lowered from 300s in May 2026" or "raised 12s→120s because a
   tight cutoff killed prefill" means a naive tweak re-opens a closed incident.
   Honor the tradeoff, don't bulldoze it.
5. **If the mechanism is wrong, STOP and re-present** — even when the fix was
   already approved. Approval was granted against the wrong model of the bug.
   Show: what the logs actually say, why it differs, and how the *implementation*
   of the approved options changes. This is the same "values correction over
   momentum" rule that applies when a task estimate proves wrong mid-flight.

## Environment note (not a durable constraint)

A repo `venv` can be missing `pip`/`pytest-timeout` such that `pytest` aborts with
`unrecognized arguments: --timeout=...` (the addopts in pyproject.toml require the
plugin). Fix, don't work around: `source venv/bin/activate && python -m ensurepip
--upgrade && python -m pip install pytest-timeout`, then run via the repo's
canonical `scripts/run_tests.sh` so the run matches CI. Establish a green baseline
before editing.

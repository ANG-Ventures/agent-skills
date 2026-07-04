# Hardening an LLM-prompt-driven cron when wiring in a new helper

When you add a new script/helper (a scorer, a cache fetcher, an enrichment step) into a
**load-bearing, agent-driven cron** — a morning brief, X-feed digest, email triage, anything
whose `prompt.md` is executed by an LLM and posts to a channel — the helper passing on its own
is NOT proof the cron is hardened. The agent's *orchestration loop around the helper* is the
real seam, and it has its own failure modes that a helper-only dry-run never exercises.

## Why the dry-run lies

The helper is a deterministic script; you can run it against real data and read its output.
That proves the helper. It does NOT prove:
- that the agent **calls the post step exactly once** (it may re-gather → re-score → re-post),
- that the agent **merges the helper's output back onto its items** (it may leave the fields null),
- that the agent **doesn't ship an empty husk** when its (now-wrong) scores clear no threshold.

These only surface when the *agent* runs the *whole prompt* on a real schedule. So: **treat the
first real scheduled run as the verification step**, and read what actually got posted (fetch the
channel) + the run's debug artifacts — don't trust "the helper dry-ran fine."

## The two mandatory guards

### (a) Single-post idempotency guard
One run = one external post. A "don't rework" instruction in prose is not enough — the agent
will still re-post to "improve / correct / add the items I missed." Add a hard marker + stop:

```bash
POSTED_MARKER="/tmp/<job>-posted-${RUN_ID}.lock"
if [ -f "$POSTED_MARKER" ]; then echo "ALREADY POSTED THIS RUN — skip"; else touch "$POSTED_MARKER"; fi
```

And in prose, explicitly: *"After the single post succeeds you are DONE posting. Under NO
circumstance call the post tool again this run — not to improve, correct, add missed items, or
repost with the helper applied. A duplicate post is a BUG and is worse than an imperfect first post."*

### (b) Merge-back-by-id step + sanity check
If the helper returns per-item output (`items:[{id, …delta…, signals}]`), the prompt must tell the
agent to **match `items[].id` back onto its candidates by the same id it sent in** and copy the
fields — otherwise the agent leaves `*_raw: null` / `delta: 0` and silently ranks on base scores.
Make the success/failure semantics unambiguous:
- `ok:true` MUST yield non-null deltas on the merged items.
- record `fired:true` when `ok:true`; `fired:false` is ONLY for timeout / `ok:false` / kill-switch.
- **Sanity check before selection:** "if the helper said `ok:true` but every candidate still shows
  `*_raw: null` / `delta: 0`, the merge silently failed — re-do the id match. A run where the helper
  fired but base scores were used is a BUG."

## Real failure — morning-digest, 2026-06-09 (first scheduled run after pf-audit wiring)

Symptom (what the user saw): a "🤷 Nothing cleared the bar today — 54 scanned, none scored ≥77" husk.

Ground truth from `#daily` + `_last_run_debug.json` + `pf-audit/log.jsonl`:
1. **4 posts in ONE cron run** (14:25:47, 14:27:28, 14:28:02, 14:28:28) with inconsistent counts
   (153 scanned then 54) — the agent re-gathered/re-scored/re-posted instead of posting once. The
   final visible message was the empty husk.
2. **pf-audit FIRED** (`log.jsonl`: `fired:true, n_items 15`) but the debug showed
   `personal_fit_raw: null`, `personal_fit_fired: false`, `personal_fit_delta: 0` on every item —
   the agent never merged the wrapper output back, so it ranked on pure base scores. Top was 76,
   below the 83 Top / 77 Also-Noted thresholds → nothing qualified → husk.

Note the helper itself was perfect (the manual dry-run the day before had shown `fired:true` on real
data). The bug was 100% in the agent's loop — exactly the part the dry-run couldn't reach.

Fix (in `~/.hermes/state/cron/morning-digest/prompt.md`, backup `.bak.*-pre-multipost-fix`):
- Step 6.5 → "SHIP IT **ONCE**" + the single-post hard guard above.
- Step 3.5 → explicit merge-back-by-id instruction + the `ok:true ⇒ non-null delta` sanity check.

## Diagnosis recipe for "the brief looks buggy"

1. Read the run summary (`_last_run_summary.json`): `posted:true` with `top:0, also:0` → it shipped
   an empty/husk digest. That's the headline bug.
2. Fetch the actual channel messages — count posts per run window. Multiple posts in one
   cron-completed window = a multi-post loop bug (not the scheduler firing twice; check
   `cron.scheduler` log lines: one "Running job" + one "completed successfully" = a single run).
3. Cross-check the helper's own log/artifacts (`pf-audit/log.jsonl`) against the per-item debug:
   if the helper logged `fired:true` but items show null deltas, it's an unmerged-output bug.
4. Confirm thresholds: if the top `final_score` < the selection floor, the husk is a *consequence*
   of the merge bug, not an independent "slow news day."

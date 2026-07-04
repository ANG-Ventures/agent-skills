# Stale-count + current-state attribution trap

**Class:** attributing a cause/contributing-actor from a log COUNT and a prior belief, without
checking WHEN the events happened or whether the actor can still act.

## The failure (the orchestrator agent, 2026-06-20)

Investigating a stuck Discord "is typing…" bubble. A co-located second bot (the backup agent) was in the
same channel. I ran:

```bash
grep -c "<channel_id>" profiles/aegis/logs/gateway.log     # -> 453
grep -c "rate-limited for <channel_id>" .../gateway.log    # -> 359
```

…saw 453 refs / 359 429s, and pattern-matched it straight onto a **memory note** ("two broad
no-mention bots in one channel = the known footgun"). I reported the backup agent as a "contributing
factor." It felt right because the memory footgun is real and recurring.

It was wrong. The user pushed back with a **channel-permissions screenshot** showing the backup agent had
no role/member grant on that (private) channel. Re-checking properly:

```bash
# Real timestamps — NOT the count. (terminal compressor had truncated my earlier head/tail.)
awk '/rate-limited for <channel_id>/{print $1}' .../gateway.log | sort | uniq -c
# -> 359  2026-06-15      (ALL five days stale; today was 06-20)
```

All 359 events were from **5 days earlier**, before the channel was locked down. the backup agent was a
**non-factor**. The convenient "it's the other bot" verdict was a stale-data artifact.

## Why it happens

- **A count is silent about WHEN.** `grep -c` / `453 refs` says nothing about recency. Big
  number → feels like strong evidence; it isn't.
- **Prior beliefs (memory notes, past footguns) are priors, not findings.** They tell you what
  to *check*, not what *is*. Pattern-matching a count onto a prior is the path of least
  resistance and skips verification.
- **Logs are historical; authority is current.** What governs whether an actor can act NOW is
  current state (permissions/ACL/config/feature flag), not week-old log volume.
- **The terminal output compressor truncates `head`/`tail`** (`[+334 more]`), so a first glance
  at first/last timestamps can be silently missing — re-run with `awk`/`sort -u` to see them.

## The check, before naming any cause/contributing actor

1. **Timestamps, not counts.** `awk '{print $1,$2}' log | sed -n '1p;$p'` (or `sort -u` the
   date field). Is the activity recent enough to be relevant to the live symptom?
2. **Current authoritative state.** Whatever gates the actor's ability to act *now* —
   permissions screen, ACL, config entry, `launchctl`/process liveness, feature flag. A
   week-old log proves the actor *did* something then, not that it *can* now.
3. **Reconcile a user contradiction toward the harder answer.** When the user pushes back with
   their own eyes (a screenshot, "that's not possible"), they are usually right — reconcile to
   the truth, don't defend the convenient verdict. (the user explicitly: trust the proven probe /
   current state over the easy "it's dead / it's the other thing" story.)
4. **Retract plainly when wrong.** State the corrected finding and *why the first was wrong*
   (stale data), so the record is honest.

## One-liner

**Logs prove what happened; they don't prove what's true now.** Ground-truth current state and
event recency before attribution — a big count plus a matching prior is a convenient verdict,
not a finding.

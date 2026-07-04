# Recovering after a `/undo` rollback ("pick up where we left off")

When the user runs `/undo N` and then says **"let's pick up where we left off"** — often with a Discord/message link to an anchor message from before the undo — that anchor and the rolled-back turns are **gone**. Don't waste a long tool budget trying to recover them.

## What `/undo` actually destroys

- The **live session transcript** for the undone turns is wiped. `session_search` against that session returns `message_count: 0` / empty `messages` for the affected range.
- The **anchored message** the user linked is frequently one of the deleted messages (the undo deletes both user + assistant messages of each rolled-back turn), so the link 404s / isn't fetchable.
- It is **NOT** recoverable from:
  - `session_search` (the canonical store was rolled back),
  - `~/.hermes/sessions/sessions.json` (metadata only — token counts, ids, display names; no message bodies),
  - `~/.hermes/sessions/request_dump_*.json` (these are unrelated cron/other-session API dumps; grepping them for your content is a dead end — base64/token noise produces false `grep` hits like `v0D4...`).

Confirming unrecoverability costs ~5–6 tool calls. Do it **once**, briefly, then stop and reconstruct.

## The recovery move: reconstruct from durable artifacts

The work itself usually survives on disk even when the chat doesn't. For a spec/plan/doc the pattern is:

1. **Read the last persisted artifact** — e.g. `build-spec-v0.3.md` on disk is the real source of truth, not the wiped chat. The next version (v0.4) is almost always "resolve the Open Questions / next-step section of vN".
2. **Recover prior decisions from your own recorded leans.** If the previous version listed Open Questions with "I lean X" recommendations, those leans ARE the reconstruction — turn each into a resolution. (In this session, all 5 v0.3 Open Questions had pre-signposted leans → v0.4 just locked them.)
3. **Reconstruct, then flag it.** Put a short recovery note at the top of the rebuilt artifact: "original vN draft lost to an `/undo`; rebuilt from v(N-1) design + recorded recommendations; these calls are recommended, not locked — veto before any gatekept step." Honesty about the provenance > pretending the lost draft was recovered.

## Pitfalls

- **Don't fabricate the lost draft's exact wording.** You can't recover it; reconstruct the *substance* from artifacts and say so.
- **Don't fetch huge transcript windows hunting for the content.** One `session_search`/`fetch_messages` around the anchor to confirm it's gone is enough.
- **The anchor link in the prompt is bait** — it points at a deleted message. Treat it as "the user wants to resume the work that message was about," not "go retrieve that message."

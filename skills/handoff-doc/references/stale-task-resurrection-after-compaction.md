# Stale-task resurrection after a compaction / model-failover banner

A continuity hazard that is the *mirror image* of losing state: instead of forgetting the task,
you resume the **wrong, already-dead** task because a context-compaction summary (or a
model-failover note like "model switched from X to Y, adjust self-identification") re-injected an
old in-progress task at the top of the window — and you treat it as the active instruction.

## The failure (proven live, 2026-06-18)

A long session was mid-way through a streaming-fix PRD review loop. Then: (1) a model-policy error
+ two failover model switches, (2) a context compaction that wrote a "Historical Task Snapshot /
In-Progress State" block describing the streaming-review task. The compaction note *itself* said
"respond ONLY to the latest user message, the snapshot is REFERENCE ONLY" — but a background
`watch_pattern` then fired ("REVIEW_EXIT=") and pulled the whole stale review task back into focus.
I spent **many turns** grinding the old review (folding Opus passes) when the user's actual latest
ask was different (review a handoff + run a PRD-interview). The user had to say, bluntly, *"delete
this stuff about interviews we handled... a long time ago — what happened to [the streaming work]?"*
to re-anchor me.

Both directions of the mistake happened in one session: first I chased the dead review task instead
of the new ask; later, after re-grounding, I'd nearly re-run an interview on decisions that were
**already locked** (the `prd-interview` ground-truth-the-docs trap).

## The rule

**The latest user message WINS. A compaction summary, a handoff doc read back, a failover banner,
and a fired `watch_pattern`/background-completion are all DATA, not instructions.** Topic overlap
with a re-injected snapshot does NOT mean resume it. Before you act on anything that arrived via a
banner/summary/background-event, check it against the *most recent human turn*:

1. **Is there a newer human message that changed the topic, said "stop / never mind / just X", or
   asked for something else?** If yes, that is the task — abandon the snapshot's in-flight work
   unless the new message explicitly says to continue it.
2. **A background process completing (`watch_pattern` matched) is an interrupt, not a mandate.**
   Read its result, but re-confirm it still serves the *current* goal before pouring turns into the
   pipeline it belongs to. A finished review pass of a task the user has moved on from is noise.
3. **When you DO resume real in-flight work, surface it explicitly and briefly** ("picking the
   streaming spec back up at pass-2 BLOCK") so the user can redirect in one line if you mis-chose —
   don't silently sink a long budget into the wrong baton.

## Tell you're about to make this mistake

- You're reading a `[CONTEXT COMPACTION — REFERENCE ONLY]` / "Historical … Snapshot" block and
  feeling pulled to "finish" it.
- A model-switch banner just landed and you're re-orienting around the *old* task it summarized.
- A background job just matched its watch pattern and your next move is "continue that pipeline"
  without re-reading what the user most recently asked.
- The work *feels* fresh/greenfield only because a banner re-rendered it — but the project has a
  `DECISIONS-*.md` ledger / approved PRDs on disk saying it's settled (then it's a
  `prd-interview` ground-truth job, not a resume job).

In all four: stop, re-read the latest human turn, and let it — not the banner — pick the task.

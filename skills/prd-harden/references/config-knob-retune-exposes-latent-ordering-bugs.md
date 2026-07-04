# Retuning a config knob is a STRESS TEST — it exposes latent bugs the old value masked

A single config value (a slot count, a batch size, a worker count, a page limit, a
top-K, a concurrency level, a retry budget) silently *masks* whole classes of bug as
long as it stays large. The bug is latent, the tests are green, and the system looks
fine — because the masking value keeps the buggy path from ever being the load-bearing
one. The moment a user retunes that knob (usually *down*), the masked bug becomes the
dominant behavior and ships broken.

**Treat any change to a tuning knob as a hardening trigger, not a one-line config edit.**
Before declaring a knob retune done, ask: "what did the OLD value hide, and is the new
value now exercising a path the tests never covered?"

## The canonical instance: a weighted selection collapses to one bucket at N=1 (2026-06-19)

Greenhouse picked N seeds/night from a pool sorted by a promotion `class_weight`. The fill
loop did `sorted(themed + other, key=lambda it: -class_weight(it))` — a **single global sort
by weight across the combined pool.** With N=3, the theme-of-day items usually filled the
extra slots anyway, so the rotation *looked* correct. the user retuned N=3 → N=1. Now only ONE
seed lands, and it's the single highest-`class_weight` item across the *whole* pool — which is
a promoted OFF-theme class (`docs/knowledge`=1.3) — **every single night.** The Mon→dev /
Tue→docs / Wed→ops theme-of-day rotation went completely dead. The bug existed at N=3 too;
N=3 just hid it.

Root cause: a **primary-vs-secondary sort-key collapse.** The design had two ranking
dimensions — (1) theme-of-day membership, (2) promotion weight — but the code sorted by (2)
ALONE, treating (2) as primary when (1) should have been primary and (2) the tiebreak *within*
each group. Fix: `sorted([(0,it) for it in themed] + [(1,it) for it in other], key=lambda t:
(t[0], -cw(t[1])))` — group rank is the primary key, weight is secondary within each group.

Second masked bug surfaced by the same retune: a "take 1 wildcard slot, then fill the rest"
ordering, with the wildcard appended FIRST. At N=3 that's one wildcard + two themed. At N=1
with `wildcard_slots=1`, the wildcard fills the *only* slot → **every** seed is a forced
wildcard and the curated rotation never plants. Guard: take the wildcard slot only when
`0 < wildcard_slots < max_seeds`.

## The durable rules

1. **A multi-dimensional ranking must encode primary vs secondary EXPLICITLY, and be tested at
   the smallest slot count (N=1).** If selection has two+ ranking dimensions (theme + weight,
   recency + score, priority + size), sorting by a single composed scalar or by one dimension
   alone is the trap. Make the key a tuple `(primary_rank, -secondary, ...)` and write a test
   that asserts the primary dimension WINS when it conflicts with a higher secondary value —
   at `max_items=1`, where there's no room for the secondary to sneak the right answer in via
   a later slot. A pool sorted right at N=1 is sorted right at N=anything; the converse is false.

2. **For every tuning knob, test the EXTREMES, not just the default.** `max_seeds=1` and a huge
   value, `batch=1` and `batch=all`, `workers=1` and `workers=many`, `topK=1`. The default value
   is the one place a latent ordering/partition/fencepost bug is *least* likely to show, because
   the system was hand-tuned around it. The boundary values are where "fill the rest" loops,
   "take one of each" slots, and global-vs-grouped sorts diverge.

3. **A "take one special slot then fill" pattern breaks when `special_slots >= total_slots`.**
   Any "reserve K slots for category X, fill the remaining N-K from the general pool" logic has a
   degenerate case at `K >= N` where the reserved category hijacks every slot. Guard the reserve
   with `0 < K < N` (or clamp), and test the `K==N` and `K>N` boundaries.

4. **Watch for a category that's excluded from the general pool but IS the answer on some inputs.**
   Greenhouse excluded wildcard items from the `themed` pool (they're a separate slot), but Friday's
   theme-of-day *is* wildcard — so with the separate slot turned off, Friday fell through to a wrong
   class. When you partition a pool into "general" and "special," check whether any *input condition*
   makes the special set the legitimate primary set (here: the day-of-week rotation lands on the
   special category). Route accordingly and preserve the item's label (the `wildcard=True` flag for
   the report badge) instead of hardcoding it false in the general-fill branch. Dedupe picks by a
   stable identity so an item reachable via both the special slot and the general pool can't
   double-count.

## How to hunt it (add to the diff-review prompt + the hardening gap-table)

- For every `sorted(...)`/`heapq`/`max(...)`/top-K in a selector, ask: "how many ranking
  dimensions does the DESIGN have, and does this key encode all of them with the right
  precedence?" A single-scalar key over a multi-dimensional design is the prime suspect.
- For every config knob the user can set, add a gap-table row: "tested at the default value? at
  the MINIMUM (1)? at the maximum?" An untested extreme is an untested claim.
- For every "reserve K / take-one-of-X then fill" loop, add the `K >= N` boundary case.
- RED-prove the guard: revert the tuple-key to the single-key sort (or remove the `< max` guard)
  and watch the small-N rotation/routing test fail. A guard you haven't watched fail against the
  un-guarded code is an assertion, not a proof. (Same discipline as the rest of this skill.)

This is a sibling of the "unreachable predicate per input-shape" bug in
`post-build-diff-review-solo-builds.md` — both are cases where a green suite over the *common*
shape/value hides a path that's dead or wrong for a *less-common* shape/value. There the axis was
input shape (NULL field); here it's a config knob value (N=1). Vary the **config-value axis** the
same way you vary the input-shape axis.

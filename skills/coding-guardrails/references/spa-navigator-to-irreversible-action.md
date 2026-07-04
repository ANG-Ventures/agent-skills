# Building an SPA navigator that drives toward an irreversible (spend) action

When you build an agent step that **drives a fragile single-page app (SPA) to a
checkout / payment / place-order page** so a separate guarded driver can act, the
navigator is its own safety-critical class: it must reach the page reliably WITHOUT
ever clicking the irreversible button or making a money/time/identity selection.
Proven building the fleet-shop Instacart v0.2 cart→checkout navigator (2026-06-13).

## Design the navigator as a positioner, NOT an oracle

- **Keep the "are we there?" oracle separate and authoritative.** The navigator's
  job is to MOVE the page; a distinct `_assert_on_checkout_page`-style gate decides
  whether you actually arrived. A navigator that "succeeds" wrongly must still be
  caught by the gate. Have the navigator REUSE the gate's exact predicate (same JS),
  so navigator-success and gate-success are the *same* test — the navigator can never
  "succeed" by a weaker check than the gate. Lock the reuse with a circular-import
  smoke test (both modules defer their cross-import to call time).
- **Put the navigator in its OWN module**, separate from the module that owns the
  irreversible tap. Then "the navigator never references the place-order selector" is
  a STRUCTURAL grep (a clean file), not a fragile substring search over a file that
  legitimately contains the string. Back it with an AST test that strips
  docstrings/comments and asserts no executable place-order reference.

## The loop invariants (each fixes a real fail-OPEN edge)

1. **Detect-first / idempotent.** No-op (zero clicks) if already on the target page;
   running it twice never double-advances.
2. **Whitelist forward controls, matched by EXACT name (or a documented prefix), never
   a body-text scan.** A substring match can hit a wrong button on a sibling screen.
   Assert no allowlist entry matches `/place order/i` or `/buy/i`.
3. **Blocking-selection detection runs BEFORE the forward-control search, every
   iteration.** A screen can have BOTH a "Continue" button AND a required
   address/slot/payment/login selection — clicking forward would advance THROUGH the
   selection. Fail closed instead. (Test the both-present case: zero forward clicks.)
4. **Two-tier blocking probe + ambiguous-case guard.** Your `*-required`/`add-*`
   selectors are *guessed from one probe session* — a real required screen with an
   unanticipated testid will slip past them. So ALSO probe for a GENERIC
   address/payment/delivery container: if a generic container is present AND a forward
   control is present AND you're not on the target page, that's AMBIGUOUS → fail closed
   (you might be about to click through a required selection you didn't anticipate).
   The benign panel-opener is exempt from this guard.
5. **A probe EXCEPTION ≠ a clean absence.** If a forward-control probe *throws*
   (half-rendered page), do NOT silently degrade to a lower-priority fallback control —
   fail closed. Return a `probe_failed` flag and check it.
6. **Bounded, no infinite SPA chase.** A hard `MAX_STEPS` derived from the OBSERVED
   transition count + small slack (with a relationship test), per-step timeout; cap
   exhausted → GuardError, never a hang. Click EXACTLY the cap, then stop.
7. **Stop the instant the oracle flips.** Check the oracle at the TOP of each iteration
   AND after the loop — don't keep clicking a forward control that's still present once
   you've arrived (overshoot guard).

## Live-finding gotchas (SPA-specific, will recur on other sites)

- **The "cart"/intermediate page is often a slide-out PANEL, not a URL** — and the
  destination is **deep-link-blocked** (a direct `/checkout` URL 404s / renders an
  empty shell). So the flow MUST be driven by clicking through the SPA; you can't
  shortcut it. The real entry is a panel-OPENER control (e.g. a `floating-cart-button`
  testid) that you add to the allowlist as a LAST-priority fallback (after the real
  forward buttons), so it doesn't re-toggle an already-open panel shut.
- **Empty overlay portals (`__reakit-portal` and friends) intercept clicks.** A plain
  click times out ("subtree intercepts pointer events"); a `force=True` click is
  SWALLOWED and does nothing. What works: press **Escape** first to dismiss the stray
  empty popover (Escape closes transient overlays without mutating cart/order state),
  THEN a normal click. Gate this to the benign opener entry ONLY, and run it AFTER the
  blocking-screen check (load-bearing ordering: a real required dialog would have
  already raised, so Escape can only clear empty overlays).
- **Click the panel-opener AT MOST ONCE per run.** If the panel opens but the forward
  button hasn't rendered yet and you re-find only the opener, a second click CLOSES the
  panel → oscillation that burns the whole step budget. Track `opener_clicked`; a second
  opener match → fail closed, don't re-toggle.
- **Settle after each click.** The SPA renders the next forward control only after the
  panel/animation finishes; a best-effort `wait_for_load_state("networkidle")` + a short
  fixed pause before the next probe (never raises). This means `MAX_STEPS` counts the
  opener as an EXTRA hop beyond the page-to-page transitions — size it accordingly.

## Process: a post-build Opus diff-review earns its keep on a green navigator

A green unit suite + a passing live e2e proves the HAPPY path; it says nothing about the
fail-OPEN-on-EDGE branches. On this build, after 156 green tests AND a live storefront→
checkout run, an Opus diff-review (APPROVE-WITH-CHANGES, no blockers) found 6 real edge
gaps the suite hid — the two highest being the guessed-blocking-selector click-through
(invariant #4) and the probe-exception-degrades-to-opener (#5). Run the post-build review
on already-passing navigator code and tell the reviewer to "hunt the branches the tests
don't exercise." Then re-verify LIVE after the hardening (the ambiguous-case guard could
have started false-tripping on the real flow — it didn't, because it was correctly scoped).

## Honest scope boundary

A navigator that REACHES the page but where the downstream guarded driver then fails-closed
(e.g. a tip-zero guard can't zero a preset-button tip widget with no "$0" option) is the
navigator DONE + a SEPARATE downstream gap correctly fail-closing — not a navigator bug.
Say so plainly; ship the load-bearing navigator, scope the downstream driver fix as its own
probe/build/test task. (This matches the user's "ship the load-bearing part, surface the scope
decision" preference.)

# Log effect, not lifecycle: instrumentation patterns for "ran cleanly, did nothing" bugs

## The trap

A class of bug looks like this:

- A script, hook, observer, listener, middleware, or injected module **loads successfully**.
- Its lifecycle telemetry — `attached`, `connected`, `started`, `subscribed`, `registered`, `[ScriptName] script tag executed` — appears in logs/console.
- The user's reported symptom **persists unchanged**.

Without effect-level telemetry, this is indistinguishable from "script never loaded" or "script crashed silently." So you spend the next hour debugging caching, MIME types, `extra_module_url` config, version-bump query strings, CSP, content-type headers, frontend reload propagation, browser hard-refresh ordering. None of that is the problem.

The problem is almost always: **your selector matched zero elements**, or your filter rejected the only events that mattered, or your transform fired on data that no longer existed in the shape you expected.

## Real-world example: HA sidebar icon override (2026-05-14)

Goal: override one blank icon in Home Assistant's sidebar via JS injected through `frontend.extra_module_url`.

v1 and v2 of the patch selected `a[href^="/"]` inside `ha-sidebar.shadowRoot`. Console showed `[SidebarIconFix] observer attached` cleanly on every page load. Icon stayed blank. Hours lost re-checking:

- Was `extra_module_url` serving the file? (yes, `curl` confirmed)
- Was the version query string busting cache? (yes, `?v=2`)
- Was the script tag injected into HTML? (yes, visible in source)
- Was the MutationObserver firing? (no telemetry for this — that was the gap)
- Was the icon swap actually executing? (no telemetry for this — that was the gap)

Diagnosis arrived only after adding `log('SIDEBAR LINKS visible RIGHT NOW:', root.querySelectorAll('a[href^="/"]').length)` to the body of the override function. Output: **`0`**. The selector was wrong — HA's 2026.x sidebar uses `<ha-md-list-item type="link">` with no `<a>` wrapper. v3 selected the right element and logged the count of actual swaps, immediately confirming success.

The fix took 5 minutes once the right diagnostic was in place. The wrong diagnostic ("script loaded") cost ~90 minutes of indirection.

## The pattern

For any code that "runs as a side effect on the page/event/stream" — frontend injected modules, MutationObservers, intercepted fetch handlers, event listeners on dynamic content, middleware that filters by predicate, decorators, content-script injections — your telemetry **must** include the count of things acted on, not just the fact that you wired up.

### Minimum useful logs

- `attached, polling for target` — lifecycle (keep, but not sufficient)
- `iteration N: found K candidate elements` — **effect telemetry**
- `iteration N: matched M, skipped K-M (reasons: ...)` — predicate visibility
- `iteration N: mutated P elements` — actual writes
- After settle period: `final: P mutations applied total, last at T` — terminal proof

If P stays `0` while N grows, you have proof your selector/predicate is the bug, not the load path.

### Anti-patterns

| Anti-pattern | What it hides |
|---|---|
| Logging only at `attached` / `register` / `start` | Whether the work loop ever does work |
| Logging only on the happy path (`if matched, log`) | The "matched zero" case looks identical to "never ran" |
| Aggregating across the whole MO callback without per-item count | A single match hides 99 misses; zero matches hides everything |
| `console.debug` for the diagnostic line, info for lifecycle | Default browser console filters out the only useful telemetry |
| Trusting that "the script appears in the HTML source" means it works | Module load and module *effect* are unrelated propositions |

### Template

For an injected DOM script that mutates targets, the body should look like:

```js
const apply = (root) => {
  const candidates = root.querySelectorAll(SELECTOR);
  let matched = 0, mutated = 0;
  candidates.forEach((el) => {
    if (!PREDICATE(el)) return;
    matched++;
    if (CURRENT(el) === DESIRED(el)) return; // already correct
    APPLY(el);
    mutated++;
  });
  if (candidates.length === 0 || mutated > 0) {
    log(`candidates=${candidates.length} matched=${matched} mutated=${mutated}`);
  }
};
```

The `candidates.length === 0 || mutated > 0` guard keeps the log noise tractable: you see the zero-candidate case (which is the bug signature) and the actual-work case (which is the success signature), but not the steady-state "scanning, nothing to do" hum.

### Generalizes to

- **MutationObservers** — log node count per callback, not just `observed`
- **Intercepted fetch / WS handlers** — log per-message disposition (`passed`, `transformed`, `dropped`), not just `installed`
- **Middleware / decorators** — log per-request branch chosen, not just `registered`
- **Event listeners on dynamic content** — log per-event match count, not just `added`
- **CLI plugins / shell hooks** — log per-invocation effect, not just `loaded`
- **Content scripts in browser extensions** — log per-page matched-element count, not just `injected`

The class invariant: **telemetry at the layer of effect, not the layer of installation.**

## Connection to existing skill content

This is a concrete subcase of Phase 1 step 4 ("gather evidence in multi-component systems") and the LLM-systems mandate to instrument before guessing. The shared root cause: **the bytes/elements that actually flowed through your code are the only ground truth**; any reasoning about whether your code "should have worked" based on source-level intent is hypothesis, not finding, until effect-level telemetry confirms it.

It's also a sibling failure mode to the v2.4.0→v2.4.1→v2.5.0 claude-api-proxy saga referenced in SOUL.md: three increasingly elaborate fixes shipped while the actual diagnostic — bytes on the wire — was 50 lines of instrumentation away. Same shape: lifecycle telemetry was healthy, effect telemetry didn't exist, fixes accumulated in the wrong layer.

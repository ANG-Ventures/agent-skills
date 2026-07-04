# MV3 Chrome-extension build traps + CDP/dogfood E2E gotchas

Hard-won while building a Manifest-V3 extension replica (Svelte + Vite + @crxjs/vite-plugin,
Chrome-for-Testing E2E over chrome-remote-interface). Reusable, non-obvious traps — instances of the
SKILL.md families "a green X is not proof" and "instrument before fixing."

## 1. crxjs only bundles HTML entries it discovers from the manifest — a runtime-`getURL` page gets un-bundled silently

@crxjs/vite-plugin walks the manifest (`background.service_worker`, `options_page`,
`action.default_popup`, `web_accessible_resources`) to find HTML entry points and emit them to
`dist/`. **A page that is opened at *runtime* via `chrome.runtime.getURL("src/ui/index.html")`
(e.g. from `chrome.action.onClicked`) is NOT referenced anywhere in the manifest, so crxjs never
discovers it** — and the moment it stops being referenced, it stops shipping.

- **The exact bite (2026-06-13):** the main outliner view lived at `index.html` and was wired as
  `options_page`. Adding a *dedicated* options page meant pointing `options_page` at the new
  `options.html` — which silently removed `index.html` from the build. `vite build` exited 0; the
  JS chunk (`index.ts`) was still emitted; only the **HTML wrapper** vanished. The action's
  `getURL("src/ui/index.html")` then 404'd at runtime. A green build hid a broken extension.
- **Fix:** declare the runtime-opened page as an explicit Rollup input so it ships regardless of
  manifest references:
  ```ts
  // vite.config.ts
  build: {
    rollupOptions: {
      input: { index: "src/ui/index.html" }, // crxjs handles SW + options_page; this is opened via getURL
    },
  },
  ```
- **VERIFY by listing the emitted HTML, never by the build exit code.** `find dist -name '*.html'`
  must list *every* page the extension can navigate to (popup, options, action-opened view, any
  `getURL` target). Then open the dist HTML and confirm it has its hashed `<script>` + `<link>`
  injected. This is the extension-build cousin of "a green commit is not proof a file is tracked":
  *a green `vite build` is not proof every page shipped.*
- **General rule:** for ANY HTML page the extension reaches by `getURL`/`tabs.create`/`windows.create`
  rather than via a manifest key, add it to `rollupOptions.input` and add a dist-HTML existence check
  to the verify gate.
- **A query-string variant of the SAME page does NOT need a new input.** Opening
  `index.html?type=clone` (P-CLONE Clone View, 2026-06-15) reuses the already-emitted `index.html`
  build — the query string is read at runtime (`new URLSearchParams`), not a separate Rollup entry.
  Only add an input when the *file* differs.

## 2. A single live-E2E assertion red amid all-green is often the TEST's regex, not the feature

Driving a real Svelte UI through CDP `Runtime.evaluate({expression, returnByValue:true})` means the
assertion is a **string of JS inside a JS string inside an `.mjs`**. Regex literals in that inner
string get escaped twice; it's easy to ship `/rgb\\\\(248, ?113, ?113\\\\)/` where the doubled
backslashes never match the real `rgb(248, 113, 113)`. The feature works; the assertion lies.

- **The tell:** 35/36 green, the one red is a *string/format match* (color, class, attribute text),
  and the sibling feature using the same code path (here: favicon via the same MARK_UPDATE) is green.
  When one assertion in a family fails while the mechanism's twin passes, suspect the assertion.
- **Instrument before "fixing" the feature.** Write a ~15-line throwaway probe that opens the same
  page over CDP and prints the *raw* DOM value (`el.getAttribute('style')`, `.outerHTML`,
  `[...].map(...)`) out-of-band. If the real value is correct, the bug is the test — do NOT touch the
  feature. (2026-06-13: probe showed `color: rgb(248, 113, 113)` was applied correctly; the red was
  purely an over-escaped regex.)
  - Run the probe **inside the project dir** (or it can't resolve `chrome-remote-interface` from
    `node_modules`); a `/tmp/*.mjs` will `ERR_MODULE_NOT_FOUND`. (Bit again 2026-06-15 — the reliable
    move is `cp /tmp/probe.mjs e2e/_probe.mjs`, fix the relative `import "./harness.mjs"`, run, then
    `rm` it. Don't fight the module resolver from `/tmp`.)
- **Prefer escape-free assertions in CDP eval strings.** Instead of a regex with parens/backslashes,
  normalize and substring-match:
  ```js
  const s = (el.getAttribute('style')||'').replace(/\s/g,'');
  return s.includes('248,113,113') || s.toLowerCase().includes('#f87171');
  ```
  `.includes()` on a normalized string survives the double-encoding that regex literals don't.

## 3. `chrome.windows.create` REJECTS a window that would sit >50% off-screen — clamp bounds to the work area

Any extension that programmatically positions a window — docking a panel beside the current one,
restoring a saved layout, opening a Clone View "to the right of the initiator" — must clamp the
requested bounds to the primary display's work area. **Chrome throws
`"Bounds must be at least 50% within visible screen space."`** when `left`/`top` would push the
window mostly off-screen, and an unhandled throw leaves the user with *no window and no error* — a
silent failure of exactly the feature they invoked.

- **The exact bite (2026-06-15, Clone View):** the UI computed
  `left = window.screenX + window.outerWidth + 1` to dock the clone just right of itself. For a
  window near the screen's right edge (or in a narrow headless test display), that `left` lands
  off-screen; `chrome.windows.create` rejected it and the clone never opened. Direct `sendMessage`
  with explicit on-screen bounds worked, which is what isolated it as a *bounds* bug, not a wiring bug.
- **This is a REAL product bug, not just a test artifact.** It reproduces on a real single-monitor
  setup whenever the source window is near the right edge. The headless test display (≈800px) just
  surfaces it every time instead of occasionally.
- **Fix — clamp in the privileged layer (the SW/background), not the caller.** The window-creating
  code owns `system.display`, so clamp there even if the UI passed explicit bounds:
  ```ts
  const wa = (await chrome.system.display.getInfo()).find(d=>d.isPrimary)?.workArea;
  const maxLeft = Math.max(wa.left, wa.left + wa.width - WIN_WIDTH - 1);
  const left = Math.min(Math.max(requested.left, wa.left + 1), maxLeft);
  // ...and wrap create() in try/catch with a no-bounds fallback so a clone ALWAYS opens:
  try { return await chrome.windows.create({ left, top, width, height, ... }); }
  catch { return await chrome.windows.create({ width, ... }); } // let Chrome place it
  ```
- **General rule:** treat any caller-supplied window geometry as untrusted for placement. Clamp to
  the work area, and pair it with a no-bounds fallback so the window is never lost to a bounds throw.

## 4. Cross-window drag/move in a multi-window extension: carry the id in `dataTransfer`, not module state

When the same extension UI runs in two windows (Clone View, multiple popups) and you want drag-and-
drop *between* them, the naive same-window approach — stash the dragged node id in a module/`$state`
variable on dragstart, read it on drop — **fails across windows**: the target window's module state
is null, so its drop handler early-returns and the drop silently does nothing. (This is precisely
how Tabs Outliner's own cross-window drag is built around it.)

- **The mechanism (TO's, faithfully):** dragstart puts the payload on the **OS drag clipboard**
  (`event.dataTransfer.setData(CUSTOM_MIME, ...)`); drop reads it back
  (`event.dataTransfer.getData(CUSTOM_MIME)`) — `dataTransfer` crosses the window boundary, module
  state does not. Resolve source as `draggedId ?? parseFromDataTransfer(...)` so same-window drag
  still uses the fast path and only cross-window falls back to the clipboard.
- **`dataTransfer` is UNREADABLE during `dragover`** (only on `drop`), so the target window can't
  draw before/after/inside feedback from the payload. Broadcast the dragged id **out-of-band**
  (e.g. `chrome.runtime.sendMessage({__drag:"start", id})` → the SW relays to all views) so each
  window mirrors an `externalDragId` for `dragover` feedback, and clear it on `drag-end`. This is
  the same out-of-band-id trick TO uses (`comminicateCurrentlyDraggedIdMVCToAllViews`).
- **A single shared model makes this MUCH simpler than serializing a subtree.** If both windows
  render one shared store (here: the SW's append-only op-log), the dragged node **already exists** in
  the target window's tree — so a cross-window drop is an ordinary move/copy *by id*, no JSON-subtree
  reconstruction. Carry just the id; reserve a JSON payload in `dataTransfer` only if you must
  support cross-*instance*/backup drops (different stores). Don't port the heavyweight serializer
  when a shared model means you don't need it.
- **Dogfood it so the test can't pass via same-window state.** Dispatch a synthetic `drop` carrying
  only the `CUSTOM_MIME` payload **with no prior `dragstart` on that page** (so `draggedId` is null),
  then assert the move/copy happened. Negative control: remove the `?? parseFromDataTransfer` fallback
  and confirm *that* gate goes red while same-window drag stays green — proving the gate tests the
  cross-window path specifically.
- **Live-sync the windows.** For the moved node to appear in the *other* window promptly, the
  shared-store mutation must push to all views (broadcast a "changed" message → each view refreshes),
  not rely on a slow poll. (Same broadcast channel as the drag-feedback relay.)

## 5. Loading an unpacked extension into a REAL running Brave/Chrome (149+/137+): use CDP `Extensions.loadUnpacked`, not `--load-extension`

To install a dev build into the user's *actual* logged-in browser (compare side-by-side with a
competitor, or let them use it on their real profile) — NOT a throwaway CfT profile:

- **`--load-extension` is STRIPPED in Chrome 137+ / Brave 149+** at launch. Don't relaunch the real
  browser with it.
- **The working path:** attach over CDP (the `browser-access` `--shopping`/`--shared` launcher gives a
  debug port on the real profile), then `Extensions.loadUnpacked({path})` via raw CDP — returns the
  assigned extension `id`. Reload after a rebuild = `Extensions.uninstall({id})` then `loadUnpacked`
  again (same `key` in the manifest keeps the id stable). Open the action page with
  `Target.createTarget({url:"chrome-extension://<id>/src/ui/index.html", newWindow:true})`.
  `/json/new?<url>` is **disabled (405)** in Brave — use `Target.createTarget`.
- An unpacked ext loaded via CDP **persists only while that debug session/flag persists**; a normal
  relaunch drops it. For permanence, package a `.crx` or keep a launchd-managed debug browser.
- The real browser already running means the launcher must **fully quit + relaunch** it with the
  debug port (a second invocation just opens a tab in the existing non-debug instance → CDP never
  comes up on the port). Quit via `osascript -e 'quit app "Brave Browser"'`, wait for the proc to
  die, clear any stale `SingletonLock`, then relaunch. (2026-06-15.)

## 6. Visual/UI-parity work: deterministic PIL/NumPy pixel analysis beats (and outlives) a rate-limited vision API

When the task is "match this reference UI" and `vision_analyze` is hard rate-limited (429s) — or just
unreliable on 1px lines / small targets at downscaled screenshot resolution — **don't keep hammering
vision; measure pixels.** A stronger, re-runnable oracle, immune to rate limits. (Tree-skeleton
parity, 2026-06-15.)

- **Read the reference's actual asset colors, not your guess.** For a sprite/PNG original, open the
  sprite files with PIL and read the pixel color (`Image.open(p).convert("RGB")`, sample a known
  pixel) — ground truth. This *refuted* a plausible source-reading assumption (assumed faint cyan; the
  sprites measured opaque steel-blue `#4F6882`). The reference's bytes beat your inference.
- **Per-column line-pixel count = a continuity oracle.** To judge "are the rails continuous vs broken,"
  count near-target-color pixels per column (`mask=abs(im-target).sum(2)<tol; mask.sum(0)`); the
  tallest columns' counts quantify rail height/continuity. Compare yours vs reference numerically
  (362→624px after the fix vs reference 1372px) instead of eyeballing.
- **Crop + 2× NEAREST upscale before any vision call you DO make** — vision on a downscaled 2000px full
  screenshot reports 1px lines as "faint/broken" even when correct. Treat its "looks broken" as a
  *weak* signal against the pixel count / live-DOM truth.
- **Save the pixel-measurement script as the reusable parity GATE** — deterministic, re-runnable each
  iteration, no API spend. The visual cousin of "render it and look": render, then *measure*.
- **Dump the sprite's ALPHA/pixel SHAPE (not just its color) — two visually-different UI elements are
  often the SAME frame.** When a reference draws what looks like distinct markers per state (a `+`/`−`
  collapse box vs a "leaf" marker), print each sprite's alpha mask as ASCII
  (`for row in np.array(Image.open(p).convert("RGBA"))[:,:,3]: print("".join("#" if v else "." for v in row))`)
  and compare the shapes. (2026-06-15, Tabs-Outliner parity: this revealed the leaf
  `node_anchor_no_subnodes` sprite is the **identical 9×9 bordered box** as the collapse box — just
  *empty inside*, no `+`/`−`. Our build had drawn a tiny 5×5 nub dot on leaf rows instead, breaking the
  clean continuous box column.) The fix collapsed to "render the same box frame, empty" instead of
  inventing a separate leaf glyph — a *smaller* diff that the shape-dump justified. Reading the sprite
  geometry, not guessing from the rendered thumbnail, is what turned a vague "leaf marker differs" into
  a one-line CSS/markup change.
- **Then PROVE the continuous column live with a DISCRIMINATING dogfood gate, not a screenshot.** Assert
  over CDP that *every* row draws the box element AND the leaf rows specifically draw the empty-box class
  AND zero old-nub elements survive
  (`glyphs===rows && leafBoxes===leafRows && rows.every(r=>!r.querySelector('.leaf-nub'))`). A gate that
  only counts the always-present wrapper button (`.nodebox`) passes trivially and proves nothing — the
  teeth are in asserting the inner glyph per row-class AND the *absence* of the element you replaced.

## 7. Resolve CONFLICTING visual analyses by live-DOM measurement, not by averaging

Two independent reviewers (or two subagent runs) disagree on a visual metric — one says "rows are 2×
taller," another "ours is tighter." **Don't split the difference; go to the authoritative oracle.** For
a rendered web UI that's the **live DOM over CDP** (`getBoundingClientRect().height` on real elements),
NOT screenshot pixel-pitch (distorts at 2000px scale) and NOT source-reading. (2026-06-15: live DOM
settled it — 35px vs ~18px → ours WAS ~2× taller; the run that "corrected" me had measured scaled
screenshot pitch and was wrong.) Record which oracle settled each contradiction; keep/demote findings
by whose *reasoning* is sharper, not by vote.

## 8. Safe "rich text" in user content = styled TEXT segments, never persisted/rendered HTML

Adding bold/italic/etc to user-authored notes/labels: keep the body **plain text on disk**, parse into
typed segments at render time (`{text, style}[]`), render each as `<span class="em-bold">{text}</span>`
— Svelte/React bind `{text}` as TEXT, so `**<script>**` becomes a bold literal `<script>`: **zero
innerHTML / zero XSS surface**. A pure `parseEmphasis(str)` is unit-testable (include an HTML-as-data
case asserting the inner is preserved literally). Don't reach for `contentEditable`/`innerHTML`/
`dangerouslySetInnerHTML` for inline emphasis — a persistence + injection liability for a feature that
only needs styling.

## 9. Renaming a product/extension: separate DISPLAY strings from PERSISTED identifiers

A "rename" is two classes of string; conflating them corrupts user data:
- **Class A — display (user-visible):** manifest `name`/`default_title`/command descriptions/store
  copy, page `<title>`, `<h1>`, export titles, dev package slug. Change freely.
- **Class B — persisted / wire identifiers:** the IndexedDB `DB_NAME`, backup/export **format tags**
  (`"oldname/backup"`, `"oldname/tree"`), the custom drag MIME, and the manifest `key`. Renaming these
  **wipes saved data / breaks restore of pre-rename backups / breaks the stable id + OAuth**. Default =
  KEEP; only migrate Class B behind a deliberate, tested migration with its own spec.
- **Prove acceptance live:** after the rename, load the new build over EXISTING data and confirm the
  old saved state still loads (DB_NAME unchanged) and a pre-rename export/backup still imports (format
  tag unchanged). Drop competitor names from store copy (trademark); check the new name isn't already
  taken on the store BEFORE committing. (2026-06-15, "Project Outliner" → "Tab Tree".)

## 10. Op-log / event-sourced model makes "restore deleted" a near-free differentiator — surface it

If state is an append-only op-log replayed into a tree, a delete is non-destructive (just a
`NODE_DELETE` op) — the deleted subtree is still reconstructable. Expose it cheaply with an optional
**delete-observer** threaded into the existing `replay()` (capture the serialized subtree at each
`NODE_DELETE` with its seq+timestamp) rather than a second replay implementation (avoid the
"second copy of the fold logic drifts" trap). Restore = re-insert via the SAME append path with
**fresh ids** (collision-safe; two restores = two independent copies) and `saved:true` /
live-binding-cleared. A capability the imperative/competitor version structurally can't match — build
it as a differentiator. (2026-06-15, Tab Tree History/Trash.)

## Bonus: persistent headed review browser for the human (separate from the ephemeral test harness)

To leave a built extension open for a human to click through (vs. the test harness that kills its
browser on teardown): launch Chrome-for-Testing **headed**, with a **persistent** `--user-data-dir`
(so their tweaks survive), `--load-extension=dist --disable-extensions-except=dist`,
`--password-store=basic --use-mock-keychain` (avoids the CfT "Keychain Not Found" modal), and a
`--remote-debugging-port` so you can still drive/screenshot it. Pre-open the action page
(`chrome-extension://<id>/src/ui/index.html`) + a couple real tabs so the tree has live content.
Confirm load via `curl -s localhost:<port>/json/list` (look for your `service-worker-loader` SW and
the page targets) before telling the human it's ready. Run it as a tracked background process, not a
shell `nohup`/`&`.

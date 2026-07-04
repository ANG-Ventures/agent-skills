# Hardening a wrapper around a VENDORED BINARY — the live-walk is the only real e2e

When your code wraps a third-party CLI/binary you don't control (a vendored Go/Rust
tool, a `subprocess`-shelled helper, an installed `pp-*`/`*-cli`), the unit suite that
mocks `subprocess.run` proves your *parsing logic* against **your assumption of the
binary's output**, not against the binary. If the assumption is wrong, every mocked
test is green AND every live call fails. The mocks and the product share your blind
spot — exactly the solo-build seam trap (`post-build-diff-review-solo-builds.md`),
but the contract is with an external binary instead of a sibling module.

**The rule: a wrapper around a vendored binary is NOT hardened until you have WALKED
every wrapped subcommand against the REAL binary and recorded its actual output.**
Mocked-subprocess unit tests are necessary but never sufficient here. Budget a live
GSD walk (`prd-harden` → GSD verify-walk) that runs each wrapped command for real.

## The bug class the live walk catches (and the mock suite cannot)

Real catch (2026-06-13, fleet-shop Instacart wrapper): a 59-green mocked suite hid
**four** real contract bugs + one architectural gap, all found by running the wired
CLI against the real `instacart-pp-cli`:

1. **Output-shape divergence.** The wrapper keyed auth on `payload["authenticated"]`;
   the real binary returns `{"logged_in": true}`. Result: `auth_status()` ALWAYS
   refused → *every* live checkout falsely aborted at the precheck. The mock test
   fed `{"authenticated": false}` (the wrapper's own assumed shape) and passed.
   **Fix pattern:** accept either field (`authenticated` OR `logged_in`) and
   **normalize** to one canonical field for downstream callers, so the seam doesn't
   leak the binary's vocabulary into `_fresh_precheck`.
2. **Missing `--json` (×3: search, carts, history).** Without `--json` the binary
   pretty-prints human text; the wrapper's `json.loads` choked. `cart show` and
   `auth status` happened to pass it, masking the inconsistency until the live walk.
   **Systemic, not one-off:** when ONE wrapped read command needs a format flag,
   audit ALL of them in the same pass — grep the wrapper for every `_json_command`/
   `subprocess.run` argv and confirm the flag is present on each. A test that pins
   the exact argv (`assert seen == [["bin","search",q,"--store",s,"--json"]]`) is the
   durable lock; RED-prove it by removing the flag.
3. **Missing capability the wrapper assumed existed (architectural).** The binary
   advertises "cart ops only, no checkout/pricing" — `cart show` returns items but
   **no `total_cents`**. The wrapper's price-cap precheck required a trusted total
   the binary structurally cannot provide. This is not a typo to patch; it's a
   **scope decision** (where does the trusted price come from?) → surface to the
   user with options, don't guess. Until decided, the guard correctly fail-closes
   (refuses to place at an unknown price) — that's the right failure, not a bug.

**How to run the walk so it actually finds these:** invoke the binary directly with
`--json` / `--help` and EYEBALL the real keys (`bin auth status --json` → see
`logged_in`, not `authenticated`). Then run your wrapper end-to-end (`python -m pkg
<cmd>`) for each command and record exit code + output. Each divergence becomes a
RED test (mock the *real* observed shape) → fix → re-walk live.

## Two adjacent traps this same session surfaced

- **Silent test SKIP from a missing async plugin.** `@pytest.mark.asyncio` tests with
  no `pytest-asyncio` installed report **"N skipped"**, not failed — so real e2e seam
  tests looked green-ish and never ran. Verify your "passed" line shows **0 skipped**
  for tests you believe are load-bearing. Lock it: set `asyncio_mode = "auto"` in
  `pyproject.toml [tool.pytest.ini_options]`, and escalate the un-awaited-coro warning
  to an error (`filterwarnings = ["error::pytest.PytestUnraisableExceptionWarning"]`)
  so a future plugin-less env can't re-hide them. Also: the project's REAL deps
  (playwright, pytest-asyncio) must live in the **project venv**, not whichever venv
  happened to run the suite — a suite that green-passes only because it skipped the
  parts needing the missing dep is a false gate.

- **Anti-bot backend: ATTACH the real browser, don't LAUNCH headless.** A checkout/
  login driver that does `playwright.chromium.launch(headless=True)` is bounced by
  modern anti-bot (Forter/DataDome/Cloudflare) — the proven backend is
  `connect_over_cdp(<real-Chrome>)` to the user's already-logged-in browser (shares
  residential IP + real TLS + session cookies). See the `browser-access` skill (Tier
  1). When hardening such a driver: (a) the session-open must attach, not launch;
  (b) `close()` on an *attached* session must **detach only** — never close the
  human's context/tabs or kill their browser (gate it on an `attached` flag);
  (c) CDP-unreachable must **fail closed** (raise), never silently fall back to the
  bot-walled headless path. All three are RED-provable with fake CDP browser/context
  objects (no real browser needed for the unit test).

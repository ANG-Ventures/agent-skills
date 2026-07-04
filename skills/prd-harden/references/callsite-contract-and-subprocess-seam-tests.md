# Two reusable hardening patterns: the call-site contract test + the env-injectable subprocess seam

Both came out of hardening a fleet of scheduled scripts that shell out to a shared
delivery tool (`notify.py`) after an OpenClaw→Hermes migration. They generalize to
**any** situation where (a) many scripts call one shared tool/CLI and the contract can
drift silently, or (b) a script's only real failure surface is a `subprocess.run(...)`
you can't safely exercise against production.

---

## Pattern A — fleet-wide CALL-SITE CONTRACT test (catch a whole bug CLASS, not one defect)

**When:** you just fixed N scripts that misused a shared tool the same way (a flag that
doesn't exist, a target format the tool doesn't accept, a kwarg the function doesn't take).
Fixing the script in front of you does NOT stop the N+1th script from reintroducing it.
The durable fix is a test that makes the contract executable and scans every caller.

**Shape (proven on `tests/notify-callsites-contract.py`):**

1. **Derive the contract FROM THE TOOL'S SOURCE, never a hardcoded list.** Parse the real
   accepted surface so the test can't drift from reality:
   - CLI flags: `re.findall(r'add_argument\(\s*"(--[a-z-]+)"', tool_src)` (+ inject `-h/--help`).
   - Function kwargs: `ast.parse` the tool, walk to the `FunctionDef`, collect
     `{a.arg for a in node.args.args} | {kwonlyargs}`.
2. **Scan every caller**, including **variable indirection**. A detector that only matches the
   literal tool name (`notify.py`) has a blind spot: real scripts do `NOTIFY=.../notify.py`
   then `python3 "$NOTIFY" --send …`. First collect vars bound to the tool path
   (`^\s*([A-Za-z_]\w*)\s*=\s*["']?[^"'\n]*toolname`), then match `$VAR` / `"$VAR"` / `${VAR}`
   uses too. **This gap is easy to ship — I shipped it mid-hardening and only caught it because
   the RED proof didn't trip.** Always RED-prove (see below).
3. **Only inspect args AFTER the tool token on the line.** Otherwise a guard like
   `[ "$1" = "--notify" ] && python3 "$NOTIFY" …` false-positives on the script's own
   `--notify` flag. Split the line at the tool token (`max()` over candidate tokens to handle
   a guard *before* the real call) and scan only the tail.
4. **Assert the gate still has teeth.** Run the tool with a known-bad flag and assert the
   strict-argparse `exit 2` — proves the whole class can't pass silently.
5. **Skip-with-documentation for known-broken DORMANT callers.** A script that violates the
   contract but is NOT scheduled (no launchd plist / cron entry) can't cause a live failure.
   List it in a `KNOWN_BROKEN_DORMANT` set with the bug named, and add a **4th check that fails
   if it ever gets scheduled** (grep the launchd dir + `jobs.json` for its stem). That keeps the
   skip honest: the day someone wires it up without fixing it, the test goes red.

**RED proof (non-negotiable):** reintroduce one original bug (`--agent forge` + a `#name`
target) into one real script, run the test, confirm it FAILS naming `file:line`, then restore
and confirm GREEN. A contract test that can't fail against the bug it was written for is
worthless.

---

## Pattern B — env-injectable SUBPROCESS SEAM for an e2e that exercises the real `subprocess.run`

**When:** the bug lives in a `subprocess.run(cmd, timeout=N)` call (a wrong timeout, a wrong
binary path, a quoting/argv-size issue) and you want an e2e that drives the *real* subprocess
path — not a mock of it — but can't hit the production dependency.

**Shape (proven on `scripts/morning-brief.py` + `tests/morning-brief-delivery-e2e.py`):**

1. **Make the binary AND the timeout env-overridable, prod defaults unchanged:**
   ```python
   DELIVERY_TIMEOUT_S = int(os.environ.get("JOB_DELIVERY_TIMEOUT_S", "90"))
   notify = os.environ.get("JOB_NOTIFY_BIN", os.path.expanduser("~/.hermes/scripts/notify.py"))
   subprocess.run(["/usr/bin/python3", notify, "--send", msg, ...], check=True, timeout=DELIVERY_TIMEOUT_S)
   ```
   When the env vars are unset, behavior is byte-identical to before (verify the prod default
   in the test: `assert mod.DELIVERY_TIMEOUT_S == 90`).
2. **The stub is a tiny generated binary you control:** writes its received payload to a temp
   file, `time.sleep(s)` to simulate latency, `sys.exit(code)`. Point `JOB_NOTIFY_BIN` at it.
3. **The e2e cases ride the real seam:**
   - RED regression: tight timeout vs a slow stub → `subprocess.TimeoutExpired` (the original bug).
   - GREEN: generous timeout completes; assert the **full** payload reached the stub byte-for-byte.
   - NEGATIVE: stub exits non-zero → `CalledProcessError` (a half-delivery must look like failure).
4. **Load the hyphen-named script as a module** to call its function directly:
   `importlib.util.spec_from_file_location(...) → module_from_spec → loader.exec_module`.

**The lesson that motivated it (durable):** a `subprocess.run(..., timeout=N)` consumer must
size `N` for the **worst-case multi-chunk** send, not a single call. A delivery tool that splits
over-limit messages into several sequential API calls (each with its own pace + possible 429
backoff) turns a "1 message ~1s" assumption into a ~14s baseline that spikes past a tight cap
under load — and the send dies **after** the work was built, a textbook silent failure. Rule of
thumb: `timeout ≥ hard_cap_chunks × (per-send ceiling + inter-send pace + 429 headroom)`. A short
test string will NOT reproduce this — the e2e must use a realistic over-limit payload.

---

## Cross-cutting pitfalls

- **A "monitor" that itself fails silently is the worst class.** This session, the gateway-
  independent cron-health monitor surfaced that `mem0_monitor.py` (a usage monitor) had been
  dying every run on a `ModuleNotFoundError` after its `notify` import path moved during a skill
  migration. Lesson: when a shared helper/skill dir relocates, every caller importing via the
  OLD path breaks silently — grep the whole fleet for the old path, and prefer importing via a
  **stable symlink entrypoint** (`~/.hermes/scripts/notify.py`) over the moving skill-dir path.
- **Concurrent sibling sessions can sweep your uncommitted edits into THEIR commit.** If a
  `git commit` reports "nothing staged" right after you staged real changes, don't assume failure
  — verify your edits landed in `HEAD` (`git show HEAD:path | grep <your change>`) and that
  `origin/main == HEAD` before re-committing. The work may already be pushed under another message.
- **Allowlist `.gitignore` repos hide test/script dirs.** A `*`-then-`!allowlist` repo silently
  won't track `tests/`, `scripts/**/` subdirs, or `cron/scripts/` until you add `!` rules — and a
  naive `!scripts/**` will pull in a vendored `.venv` (2000+ files). Add the allowlist rule, then
  `git add --dry-run` and grep for `venv` before committing; exclude it explicitly.

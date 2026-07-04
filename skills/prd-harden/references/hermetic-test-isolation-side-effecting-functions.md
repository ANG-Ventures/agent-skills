# Hermetic test isolation for side-effecting production functions

**Load when:** a test calls a real production function that **writes operator
state** (a hash/cursor/cache file under `~/`), **spawns an external notifier**
(Telegram/Discord/`notify.py`, email, webhook), or otherwise **reaches outside
the test sandbox**. The bug class: a non-hermetic test silently mutates real
state and/or fires a **real live alert** every time the suite runs.

This is the failure that looks like the *environment* changed but was actually
**self-inflicted by the test suite.** Worked example below cost a confusing
"is Anthropic changing their policy?" investigation — the answer was "no, our
own `npm run verify` fired the alerts."

---

## The smell

A test like this:

```js
test('maybeAlertOnFingerprintChange handles missing notify gracefully', () => {
  // notify.py is at ~/.hermes/scripts/notify.py — assume present on the dev box
  fpAlert.maybeAlertOnFingerprintChange(tplA);   // <-- REAL function, NO isolation
  assert.strictEqual(threw, false);
});
```

Two things this *actually* did, neither intended:

1. **Wrote the operator's real state file** (`~/.hermes/.../fingerprint-last-hash`)
   with a test fixture → the next real process saw "state changed" and reacted.
2. **Spawned the real notifier** → a live Telegram/Discord alert fired, in
   production, from a unit test.

The tell that it's self-inflicted, not the environment:
- The suite emits the side effect **only when run** (alerts cluster at the
  minute `npm run verify` ran; mirror-image add/remove pairs).
- A magic constant in the alert payload (a round timestamp, an old version
  string, a stale UA) exists **in exactly one place in the repo: the test
  fixture.** `grep -rn "<that value>" .` lands on the test file. That grep is
  the fastest root-cause — do it first.

## Why it hides

- The happy path is green (the function "doesn't throw"), so unit coverage looks
  fine. The side effect is invisible *in the test* — it lands in `~/` and on a
  chat channel, not in an assertion.
- A **dead isolation helper** is often present but never wired in (`withTempHashFile()`
  defined, never called). Its existence makes a reviewer assume isolation that
  isn't happening. Delete dead helpers; don't trust their presence.

## The fix — three moves

### 1. Make the production module's external paths resolve at CALL time via env

Module-load-time `const HASH_FILE = join(homedir(), …)` is untestable without
re-`require` gymnastics. Resolve through a function that reads env each call,
keeping the default identical so **production behavior is unchanged when unset**:

```js
const DEFAULT_HASH_FILE   = join(homedir(), '.hermes', 'app', 'state-file');
const DEFAULT_NOTIFY      = join(homedir(), '.hermes', 'scripts', 'notify.py');
function hashFilePath()  { return process.env.APP_STATE_FILE   || DEFAULT_HASH_FILE; }
function notifyScript()  { return process.env.APP_NOTIFY_SCRIPT|| DEFAULT_NOTIFY; }
function alertsDisabled(){ return process.env.APP_DISABLE_ALERT === '1'; }
// keep back-compat exports: const HASH_FILE = DEFAULT_HASH_FILE; (reflects default)
```

Then **use the accessor everywhere** the old constant was used (read, write,
spawn) — grep for the old constant name to be sure none slip through.

### 2. Add an operator kill-switch checked BEFORE any write or spawn

The disable check must short-circuit *before* the first state write (including
the "baseline" write) and before the notifier spawn:

```js
function maybeAlertOnChange(x) {
  if (!x || !x._version) return;
  if (alertsDisabled()) { console.log('alerts disabled via APP_DISABLE_ALERT'); return; }
  // …only now read prior state, diff, write, spawn notifier…
}
```

This doubles as a real operational knob: set `APP_DISABLE_ALERT=1` in a dev/CI
host's service env so it never alerts; leave it unset in production.

### 3. Make the test hermetic — set env to a temp dir BEFORE requiring the module

```js
const TEST_DIR = fs.mkdtempSync(path.join(os.tmpdir(), 'app-iso-'));
process.env.APP_STATE_FILE    = path.join(TEST_DIR, 'state-file');
process.env.APP_NOTIFY_SCRIPT = path.join(TEST_DIR, 'notify-DOES-NOT-EXIST.py');
process.env.APP_DISABLE_ALERT = '1';
process.on('exit', () => { try { fs.rmSync(TEST_DIR, {recursive:true,force:true}); } catch {} });

const app = require('../../src/the-module.js');   // <-- require AFTER env is set
```

Set env **before** the `require` (or before the function uses the accessor —
the call-time accessor pattern makes ordering forgiving, but set-before-require
is the safe default). Delete any dead isolation helper.

## Regression guards (RED-provable)

Add tests that **fail if the module ever resolves the real path again**:

```js
test('module honors env-redirected state file (never the real one)', () => {
  assert.strictEqual(app.hashFilePath(), process.env.APP_STATE_FILE);
  assert.notStrictEqual(app.hashFilePath(), app.DEFAULT_HASH_FILE);
  app._writeStateForTest(fixture, hash);
  assert.ok(fs.existsSync(process.env.APP_STATE_FILE)); // landed in temp, not ~/
});

test('kill-switch suppresses all alert work before any write/spawn', () => {
  const f = process.env.APP_STATE_FILE; fs.rmSync(f, {force:true});
  app.maybeAlertOnChange(divergentFixture);   // would normally fire
  assert.strictEqual(fs.existsSync(f), false); // short-circuited before baseline write
});
```

## Prove it's actually fixed (the real verification, not a synthetic proxy)

The acceptance test is: **a full suite run does not touch the real state file.**

```bash
cp ~/.hermes/app/state-file /tmp/state.before
npm run verify
diff -q /tmp/state.before ~/.hermes/app/state-file \
  && echo "✅ real state UNTOUCHED by verify" \
  || echo "❌ STILL MUTATED"
```

Run this *before and after* the fix so the diff proves the bug existed and is
gone. (Before the fix it differs; after, it's identical.) This is the
"verify against the original conditions" rule — the symptom was "verify mutates
real state and alerts," so the proof is "verify no longer does."

## Deploy note (when the fix is runtime code on a fleet)

If the side-effecting module is loaded by a long-running service on multiple
hosts, the fix is a **runtime change** — it must be redeployed to every host
running the service, and verified by checking the **fix code is present**
(`grep -c APP_DISABLE_ALERT src/the-module.js`) not just the version string.
After restart, also confirm no *straggler* alert can fire: the stored state and
the freshly-computed state should hash-match (a restart that re-detects a real
change WILL legitimately alert once — make sure that's the only path left).

## Variant — recording-stub-SCRIPT seams to test a fail-open alert ESCAPE path

When the side-effecting function isn't JS-with-an-accessor but a **real alert sender that shells out**
to one-or-more delivery binaries with a *primary → fallback* escape (queue-shim first, raw-notify on
ANY shim failure), the hermetic harness is a pair of **executable recording stubs** pointed at via the
function's existing env seams. Caught 2026-06-14 hardening `fleet_alert.py` (pipecat-house-voice), which
had **zero tests** despite owning the single most important safety property of the cron-alert cutover:
*a box-down event must never go silent.*

The pattern:

```python
def _make_stub(path, exit_code, record, *, lang="bash"):
    """Stub that appends its argv to `record` and exits `exit_code`.
    Match the LANGUAGE to how the function invokes it: the queue shim is run as
    `bash shim ...` → bash stub; notify.py is run as `python3 notify.py ...` → python stub.
    (A bash stub for a `python3 X` call fails to exec and silently corrupts the test.)"""
    body = (f"#!/usr/bin/env python3\nimport sys\n"
            f"open({record!r},'a').write(' '.join(sys.argv[1:])+'\\n')\nsys.exit({exit_code})\n"
            if lang == "python" else
            f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> {record!r}\nexit {exit_code}\n')
    open(path, "w").write(body); os.chmod(path, 0o755)
```

A context manager scrubs the real seam env vars, writes the two stubs into a tempdir, and points
`FLEET_ALERT_QUEUE_SHIM` / `FLEET_ALERT_NOTIFY` at them with chosen exit codes. Then the assertions are
about **which stub was called and which was not** (read the record files):

- `shim_exit=0` → assert `via=queue` AND the notify record is **empty** (raw fallback NOT reached).
- `shim_exit=1, notify_exit=0` → assert `via=fallback` AND both records non-empty (tried queue, escaped raw).
- the headline safety test — `shim_exit=1` (queue wedged) + a **critical** → assert the critical reached
  the raw wire; this is the box-down escape.
- `shim_exit=1, notify_exit=1` (total outage) → assert the function still **returns a marker, never raises**
  (an alerter must not take down its caller).
- routing-preservation: assert the shim received `--severity high` for a `warn` (never silently demoted to the logs channel).

**RED-PROVE the safety property by breaking the fallback, not just by passing.** An escape-path test you
haven't watched fail against broken code is an assertion, not a proof. Temporarily edit the function so
`_queue_send` returns a success marker *unconditionally* (swallowing the shim's failure), re-run, and
watch the box-down/fail-open tests go red — then restore (verify byte-identical via md5) and confirm green.

**Live-box caveat:** a "no seam configured at all" test can't be hermetic on a real host — the function's
auto-discovery finds the *real* `~/.hermes/scripts/notify`, so the test would fire a real alert or assert
the wrong path. Reframe "missing seam" to the realistic **box-down condition** (seam present but the
binary exits non-zero — a locked/unwritable DB), which is what actually happens in production.

## Checklist

- [ ] `grep -rn "<magic value from the alert payload>" .` → does it land on a test fixture? (root-cause)
- [ ] External paths resolve at call time via env, defaults unchanged.
- [ ] Kill-switch checked before the first write AND the notifier spawn.
- [ ] Test sets env to a temp dir before `require`; dead isolation helpers deleted.
- [ ] Two regression guards: honors-env-path, kill-switch-short-circuits.
- [ ] Snapshot-diff proof: full suite run leaves the real state file byte-identical.
- [ ] If runtime code: redeployed to all hosts, fix code grep-confirmed, no straggler alert.

# Hardening a launchd/cron SHELL script — make it testable with injection seams

Fleet healthcheck/watchdog/autoheal scripts (the `ai.agent.*-healthcheck` launchd family:
token-refresh, cert-healthcheck, tccd-self-heal, codex-lane-health, …) are load-bearing shell.
The naive version runs top-to-bottom calling real `codex`/`ps`/`kill`/`notify.py` against real
state — which means you **cannot test its failure paths** without breaking the real system. That
is the hardening gap: a script whose whole job is to catch silent failures, itself untestable.

The fix is the same DI pattern you'd use in any language, adapted to bash: **extract the logic
into functions, inject every external dependency via an env override, and add a source-only guard
so a test can load the functions without running `main`.** Then write RED-provable tests that
stub the dependencies and assert each failure path.

## The seam pattern

```bash
# 1. Every external dependency is an overridable variable, defaulting to the real thing.
AUTH_JSON="${MYJOB_AUTH_JSON:-$HOME/.codex/auth.json}"   # file path → point at a fixture
CODEX_CMD="${MYJOB_CODEX_CMD:-codex}"                     # binary → point at a stub script
PS_CMD="${MYJOB_PS_CMD:-ps}"                              # binary → stub emitting fixture lines
KILL_CMD="${MYJOB_KILL_CMD:-kill}"                        # destructive op → stub that RECORDS pids
NOTIFY="${MYJOB_NOTIFY:-$HOME/.hermes/scripts/notify.py}" # alert → point at /nonexistent in tests
ALERT_SINK="${MYJOB_ALERT_SINK:-}"                        # tee alert bodies to a file the test reads
DRY_RUN="${MYJOB_DRY_RUN:-0}"                             # do-everything-but-mutate switch

# 2. Side-effecting steps honor DRY_RUN + ALERT_SINK so tests observe intent without effect.
fail_alert() {
    local body="$1"
    [ -n "$ALERT_SINK" ] && printf '%s\n' "$body" >> "$ALERT_SINK"   # test asserts on this
    [ "$DRY_RUN" = 1 ] && { log "DRY: would alert: $body"; return 0; }
    [ -f "$NOTIFY" ] && python3 "$NOTIFY" --send "$body" --channel discord --target "$CHAN" \
        || logger -t "$TAG" "alert: $body"
}

# 3. Pure-ish logic lives in functions that take their inputs as args (testable in isolation).
read_expiries() { python3 - "$1" <<'PY' …decode JWT exp… PY ; }   # arg = auth.json path
reap_orphans()  { python3 - "$1" "$2" "$3" "$4" <<'PY' …ps→parse→kill… PY ; }  # ps,kill,age,dry

main() { … orchestrates the functions … }

# 4. The source-only guard: tests `source` the script for its functions WITHOUT running main.
if [ "${MYJOB_SOURCE_ONLY:-0}" = "1" ]; then
    return 0 2>/dev/null || true    # sourced: stop here, functions are now defined
else
    main; exit $?                   # executed normally: run
fi
```

## The test harness shape

```bash
# Build fixtures (a fake auth.json with a chosen token lifetime; stub codex/ps/kill scripts).
make_auth()  { python3 - "$1" "$2" <<'PY' …emit JWT with exp=now+offset… PY ; }
make_ps_stub() { { echo '#!/bin/bash'; printf 'cat <<PSEOF\n%s\nPSEOF\n' "$1"; } >"$2"; chmod +x "$2"; }
make_kill_stub() { printf '#!/bin/bash\necho "$@" >> %q\n' "$REC" >"$1"; chmod +x "$1"; }

run() {  # run the real script under a clean injected env; capture rc + out + err
    env MYJOB_AUTH_JSON="$1" MYJOB_CODEX_CMD="$2" MYJOB_PS_CMD="$3" MYJOB_KILL_CMD="$4" \
        MYJOB_ALERT_SINK="$5" MYJOB_NOTIFY=/nonexistent bash "$SCRIPT" >out 2>err; echo $?
}
# Then: assert exit code, assert the ALERT_SINK got the expected body, assert KILL_REC has/lacks a pid.
```

## What to test (the failure surface of a healthcheck script)

| Path | Test | Guards against |
|---|---|---|
| fixture file missing | missing → alert + rc1 | crash / silent no-op on a vanished credential |
| fixture corrupt | bad JSON → parse-error alert + rc1 | unguarded `jq`/parse crash |
| value within action window | triggers the heal step (+ escalation if heal didn't take) | not acting when it should |
| dependency probe reports bad | `doctor`/health stub fails → alert | silent degraded state (the original bug class) |
| destructive op — target qualifies | aged+idle proc → kill RECORDED | reap path silently doing nothing |
| destructive op — target is YOUNG | below-threshold → NOT killed | killing live work (an outage you caused) |
| destructive op — target is BUSY | high-CPU → NOT killed | same |
| destructive op — wrong target | unrelated proc → never touched | a loose grep nuking innocent procs |
| happy path | fresh state → exit 0, NO alert, "ok" logged | a script that cries wolf every run |

## Prove the tests have TEETH (RED-provability, the prd-harden non-negotiable)

A green suite proves nothing if the tests can't fail. **Spot-check 1–2 critical guards by breaking
them and confirming the matching test goes RED**, then revert:

```bash
cp script.sh /tmp/broken.sh
sed -i '' 's/cpu < 1.0/cpu < 100.0/' /tmp/broken.sh         # neuter the busy-proc guard
SCRIPT=/tmp/broken.sh bash test.sh | grep -E 'busy|RESULT'  # → that test must now FAIL
```

If breaking the guard doesn't turn a test red, the test is green-by-construction and worthless.

## Pitfalls that bit (codex-lane-health, 2026-06-10)

- **macOS BSD `ps` has NO `etimes` keyword** (Linux-only). A reap loop reading `etimes` silently
  parses nothing and reaps nothing — a hardening test (an aged-proc fixture) is exactly what
  catches it. Use `ps -axo …etime…` (BSD `[[DD-]HH:]MM:SS`) and parse it to seconds in Python.
- **Instrument the real state before coding the guard.** The codex `id_token` `exp` sits chronically
  in the past by design; only the `access_token` gates the lane. Gating refresh on the wrong token
  fires every single run. A 10-min observation of the real `auth.json` killed the wrong design.
- **The redaction layer masks `$(…)` command-substitution as `***` in shell you write via
  write_file/patch** — verify the on-disk bytes (`[ord(c) for c in line]` via execute_code) before
  trusting the displayed source; the bytes are usually correct even when the display shows `***`.
- **Back up + commit the script and its test together**, push to the repo (scripts live in a
  git-tracked tree even when `skills-shared`/`launchd` are gitignored — check `git check-ignore`).

# Swallowed structural error → fake-FAIL; force the full traceback before theorizing

The fake-green traps in the main SKILL have an evil twin: a **fake-FAIL**. A broad
`except Exception as e:` that turns the error into a *score* or a *string field*
hides a structural failure (wrong interpreter, broken import, missing dep) and
makes a metric read 0/N — so you misread a *setup/wiring* problem as a *behavioral*
one and start "fixing" the wrong layer. Worse, the swallowed string can look like a
plausible runtime error, sending you down a confident-but-wrong root-cause path.

## The 2026-06-17 worked example (LCM Arm-B node-recovery harness)

Symptom: a live recovery harness scored **0/N node-served recall** across several
runs. Each per-trial record carried `node_served_answer: "[recovery error: 'type'
object is not subscriptable]"`.

What I did WRONG (two full rounds):
1. Theorized it was a **concurrency bug in the engine** (`response.choices[0]`
   racing the gateway), and even shipped a defensive guard + regression tests for
   a real-but-unrelated unguarded access. Plausible, committed, **not the cause.**
2. Re-ran; still 0/N. Re-theorized contention timing, added a DB-settle guard.
   Still 0/N.

What actually found it: **forcing the real traceback** instead of trusting the
swallowed string. I wrapped the call to re-raise and print `traceback.print_exc()`:

```
File ".../plugins/context_engine/lcm/config.py", line 12, in <module>
    def _parse_pattern_list(raw: str) -> list[str]:
TypeError: 'type' object is not subscriptable
```

Root cause: `python3` on this fleet resolves to **anaconda Python 3.7.4**
(PATH-poison). 3.7 cannot parse `list[str]` annotation syntax, so the harness'
*in-process import of the engine* died at import time. The broad `except` in the
recovery loop stringified that import error into a fake per-trial "[recovery
error]" and scored it 0/N. The engine, the DAG, condensation — all working the
whole time (those run via CLI subprocesses on a sane interpreter). Manual probes
"passed" only because `execute_code` runs under 3.11; every *subprocess* run used
3.7. The "intermittent" failure was never intermittent — it was 100%
interpreter-determined.

## The rules this encodes

1. **A swallowed error is not a result. Force the real traceback before forming
   any root-cause hypothesis.** When a metric reads 0/N or a field holds an error
   string, your FIRST move is to re-raise / `traceback.print_exc()` and read the
   actual stack — not to theorize about what the stringified message "probably"
   means. One `print_exc()` would have saved two wrong fix rounds here.

2. **`except Exception` around the load-bearing call is a fake-FAIL factory.**
   Catching everything and scoring it as a per-trial miss silently converts
   *structural* failures (ImportError, SyntaxError, wrong interpreter, missing
   binary) into *behavioral* zeros. Fix: catch structural errors separately and
   **abort the run loudly** — they are not a data point, they're a broken harness:
   ```python
   except (ImportError, SyntaxError, ModuleNotFoundError) as exc:
       raise RuntimeError(f"FATAL structural error (not a result): {exc}") from exc
   except Exception as exc:               # genuine per-item failure → score it
       record = f"[error: {exc}]"
   ```

3. **A 0/N or all-fail metric is suspiciously TOO uniform — suspect the harness,
   not the system under test.** Real behavioral failures scatter; a clean 0/N
   (every single trial failed identically) is the signature of a wiring/setup
   break upstream of the thing you're measuring. The same logic as "a clean 100%
   pass is suspicious" — uniformity at either extreme points at the rig.

4. **Manual probe passes ≠ subprocess passes when the interpreter differs.** If
   in-process / `execute_code` tests pass but the spawned-subprocess run fails,
   suspect the interpreter/env the subprocess inherits FIRST. `which -a python3`
   and compare `--version`; pin the known-good interpreter (e.g.
   `<repo>/venv/bin/python`) explicitly in the runner, never bare `python3`.

5. **Guard the interpreter at the top of any script that imports modern-syntax
   code in-process.** Fail loud with the fix, don't let it import under a broken
   interpreter:
   ```python
   if sys.version_info < (3, 9):
       sys.stderr.write(f"FATAL: needs py>=3.9; got {sys.version.split()[0]} "
                        f"at {sys.executable}. Use <repo>/venv/bin/python ...\n")
       raise SystemExit(3)
   ```

## Honesty footnote

When you've shipped a "fix" for a hypothesis the traceback later disproves, say so
plainly and correct the framing — don't let an overclaiming commit message stand.
The defensive guard may still be worth keeping as hardening, but it is NOT "the
fix," and the record should say which.

## Fleet-specific tripwire

On the user's Macs, bare `python3` = `/opt/anaconda3/bin/python3` = **3.7.4**. Any fleet
harness/script that imports py3.9+ code in-process MUST use the project venv
(`~/.hermes/hermes-agent/venv/bin/python`). This is the same 3.7-PATH-poison noted
elsewhere in fleet memory; the `'type' object is not subscriptable` at *import* of a
`list[str]`-annotated module is its fingerprint.

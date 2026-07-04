# Hardening a new optional kwarg threaded through injected-runner / stub seams

When you add a new optional parameter (a `cookies=`, `proxy=`, `timeout=`, `auth=`) and thread it
**down a call chain** that already has a dependency-injection / monkeypatch seam, the back-compat
failure mode is sharp and easy to miss: existing test stubs and injected runners were written for the
OLD signature and will crash — or worse, get silently swallowed — the moment production starts
calling them with the new kwarg.

Proven on the YouTube→NotebookLM pipeline (2026-06-09), threading `cookies=` from
`ingest()` → `transcribe_one()` → `_try_asr` → `chunked_transcribe.probe_duration` + `acquire_audio`,
and adding a `--limit N` hard cap to a CLI whose `run()` already had injectable helpers.

## The two failure modes this pattern prevents

### 1. Injected runners written for the old signature crash on the new kwarg
A function that accepts injectable callables for testability —

```python
def transcribe_chunked(target, *, probe=probe_duration, acquire=acquire_audio, cookies=None):
    ...
    audio = acquire(target, workdir, cookies=cookies)   # BREAKS every 2-arg stub
```

— cannot blindly forward the new kwarg, because half the test suite injects 2-arg stubs
(`lambda t, w: ...`) and real legacy callers pass 2-arg `acquire` functions. Blindly forwarding
raises `TypeError: got an unexpected keyword argument 'cookies'`.

**Fix: a signature-aware forwarder.** Only pass the new kwarg to callables that actually accept it
(named param OR `**kwargs`); otherwise drop it silently. This keeps the injection seam
back-compatible while still threading auth to the real default impls.

```python
import inspect

def _maybe_cookies(fn, cookies):
    if cookies is None:
        return {}
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    if "cookies" in params or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    ):
        return {"cookies": cookies}
    return {}

# call site:
audio = acquire(target, workdir, **_maybe_cookies(acquire, cookies))
```

Lock it with a dedicated test that injects a **legacy 2-arg runner** and asserts the call still
succeeds (the new kwarg is silently dropped, not forwarded).

### 2. Monkeypatched stubs with a narrow lambda silently mis-route
The more insidious one. A test does `monkeypatch.setattr(mod, "probe_duration", lambda t: 60.0)`.
Once production calls `probe_duration(target, cookies=cookies)`, that lambda raises — but if the
call site is wrapped in a broad `try/except` (common for "a failed probe is non-fatal, fall through"),
the exception is **swallowed** and the code takes the WRONG path (single-shot instead of chunked,
wrong backend label, etc.). The test then fails on a confusing downstream assertion, not on the
actual `TypeError`.

**Fix:** when you widen a production signature, widen every stub that monkeypatches it in the same
diff: `lambda t: 60.0` → `lambda t, **k: 60.0`. Grep the test tree for the patched symbol
(`grep -rn '"probe_duration", lambda' tests/`) and fix ALL of them, including autouse-fixture stubs.

The tell that you hit this: a test that *used* to pass now fails on a value/path assertion (not a
TypeError) right after you added the kwarg — the stub is eating the exception.

## Caller back-compat at the top of the chain
At the loop/dispatcher that fans out to the patched function, make the new kwarg **conditional** so
legacy stubs that take only positional args keep working:

```python
cookies_kw = {"cookies": cookies} if cookies is not None else {}
result = transcribe.transcribe_one(vr, mode, **cookies_kw)   # legacy stub: transcribe_one(vr, mode)
```

`_accepts_keyword(fn, "cookies")`-style guards in the CLI's `_call_*` helpers do the same job for the
real entrypoint.

## Precedence rule for param-vs-env
When the new kwarg duplicates an existing env-var contract (e.g. `cookies=` vs `YTNB_YTDLP_COOKIES`),
make the **explicit param win, env stay an honored fallback**, and write three tests:
explicit-param-only (no env), env-only (no param → fallback still works), and param-beats-env. This
proves you closed the gap *without* breaking the env contract that crons/CLIs already depend on.

## The end-to-end regression lock
Threading "works" only when the value reaches the real subprocess at the bottom. A unit test that the
kwarg is *passed* is necessary but not sufficient. Add (or repoint) a **live/e2e test that scrubs the
old env contract** (`monkeypatch.delenv(...)`) and passes the value ONLY via the new param — so if the
threading ever regresses, the real path (which needs the auth to get past the gate) fails fast. This
is the strongest proof that the param actually flows all the way down.

## CLI "hard cap vs prompt-gate" distinction (related, same session)
When a CLI has a confirm-gate threshold (`--max-videos`: *prompts* when expansion exceeds N) and you
add a true hard cap (`--limit N`: *truncates* the work), the gate must reason about the **post-limit**
count, not the raw expansion — otherwise `--limit 10` on a 1000-item source still trips the prompt.
Order is **expand → limit → gate → execute**. Tests: limit-under-gate never prompts; limit-above-gate
still prompts on the capped count; `limit <= 0` rejected with a clear `ValueError`.

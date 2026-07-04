# Editing live source on a REMOTE host without the redaction layer mangling it

When the code you must change lives on a remote box (a live service host you reach over SSH —
e.g. the the Linux GPU box pipecat hub at `<user>@<lan-ip>`), the Hermes file tools (`patch`/`write_file`)
operate on the **orchestrator's** filesystem, not the remote one, and any inline SSH edit risks the
secret-redaction layer mangling nested quotes / `$()` / token-shaped literals on the *tool transport*
(see SKILL.md "the redaction-layer trap"). The clean, repeatable pattern proven across a multi-file
live-hub build (2026-06-17, voice-turn telemetry: edits to `router_dispatch.py`, `bot.py`,
`reply_player.py`, `riva_segmented_stt.py`, `ha_tts_speak.py`):

## The pattern: author a Python EDITOR script locally, scp it, run it on the host

1. **Write a small idempotent Python editor with `write_file` (local /tmp).** It does literal
   `src.replace(OLD, NEW, 1)` swaps, each guarded by `assert OLD in src, "anchor not found"` and a
   final `assert src != orig`. Build OLD/NEW from normal Python string literals — they live in a
   *file you wrote*, not an inline command, so the redactor doesn't touch them.
2. **`scp` the editor to the host, run it with the host's interpreter, then syntax-check:**
   ```bash
   scp -i ~/.ssh/id_ed25519 -o StrictHostKeyChecking=no /tmp/edit_foo.py ace@HOST:/tmp/edit_foo.py
   ssh ... ace@HOST 'cd <repo>/server; python3 /tmp/edit_foo.py && \
     /path/to/venv/bin/python -m py_compile processors/foo.py && echo PY_OK'
   ```
3. The editor prints boolean confirmations (`"timing param:", "timing=None," in src`) so you SEE each
   swap landed without trusting the display.

## Why NOT the cheaper forms (each failed this session)

- **`patch`/`write_file` against a remote path** — edits the wrong filesystem (the orchestrator's),
  not the host's.
- **`python3 - <<'HEREDOC'` over SSH / `subprocess.run(input=editor_with_triple_quotes)`** — a Python
  editor whose OLD/NEW blocks themselves contain `'''triple-quoted'''` Python source collides: the
  nesting throws `SyntaxError: invalid syntax` on the heredoc/stdin parse. **Author the editor as a
  FILE and scp it** — the file's bytes are clean; only the inline-stdin transport mangles. (This is
  the remote-source cousin of SKILL.md's "build it ON the remote host" rule for `${VAR}` configs.)
- **`git commit -m "...with (parens) or backticks or B-3'..."`** — the inline message is shell-eval'd
  and dies `eval: syntax error near unexpected token '('`. Write the message to `/tmp/msg.txt` and
  `git commit -F /tmp/msg.txt` (see SKILL.md "Shell-hostile characters in a git commit message").

## Anchor-choice traps specific to the editor pattern

- An `assert OLD in src` that finds the WRONG match silently edits the wrong place. Real bite: a
  signature insert keyed on `") -> None:"` / `):` matched a nested `def _chunks(` instead of the
  intended `__init__`, producing `def _chunks(,\n timing=None):`. Anchor on enough surrounding context
  to be unique (include the full multi-line signature, or a neighbouring unique line), and **always
  `py_compile` after** — a structural break shows up immediately.
- When adding a kwarg to a function whose signature ends in `**kwargs`, insert the new param
  *before* `**kwargs` (`stop_threshold_eou: float = -1.0,\n timing=None,\n **kwargs,`), or the body's
  `self._x = timing` `NameError`s at runtime.

## Wiring optional, FAIL-OPEN cross-cutting behavior through a processor chain

For telemetry / observability / any non-load-bearing cross-cutting concern threaded through several
processors: make the new dependency an **optional `timing=None` kwarg** at each layer, thread it from
the top builder (`bot.py`) down through the constructors, and wrap EVERY call to it in a
swallow-and-log so a bug in the concern can never break the real path:
```python
def _tmark(self, tt, stage):
    if tt is None: return
    try: tt.mark(stage)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[telemetry] mark({stage}) failed: {exc!r}")
```
The default (`None`) means existing call sites and tests are byte-unaffected; the feature only
activates where the builder passes a real object. This is the minimal-diff, zero-blast-radius shape
for "add measurement to a live pipeline."

## Per-phase commit on a live system (why it saved the build)

Each TDD phase was committed + pushed the moment its tests went green and its live-restart was clean,
BEFORE the next phase's edits. This is the standing "commit each green phase" rule, and on a live
service it's load-bearing: a later phase's experiment (or a `git checkout` slip) can't cost more than
the current phase. It also makes the live host trivially recoverable to the last-known-good tip.

## Test-isolation bite: a new test file that imports REAL deps poisons sibling stub-based tests

A new test module that does `from pipecat... import X` at top-level loads the **real** package into
`sys.modules` at collection time. A *sibling* test file that relies on `install_import_stubs()` (a
lightweight stub harness) to replace those modules then finds them already-real and its stub-install
no-ops → the sibling's permissive stub constructors (`TranscriptionFrame(text=...)`) hit the real
class's required args and fail — but ONLY when the new file collects first (order-dependent, passes
in isolation). Fix: make the new test file use the **same stub harness** the siblings use
(`install_import_stubs()` BEFORE the first `from processors...` import), so it never forces real
deps into `sys.modules`. Diagnose by running `pytest fileA fileB` vs `fileB fileA` — if order flips
the result, it's `sys.modules` pollution, not a real failure.

# Testing code buried in a god-file handler: the AST-invariant pin

## When to reach for this

Your change lands deep inside a multi-thousand-line function (a 17k-line async gateway message
handler, a giant `cli.py` command dispatcher, a monster event loop). You CANNOT unit-drive it: the
function takes dozens of args, awaits real adapters, touches global state. The two tempting wrong
moves are (a) **skip the test** ("can't reach it") or (b) **mock the entire handler** (proves the
mock, not the code). There's a third, better option the codebase often already uses: an **AST
invariant** that parses the module source and asserts the structural facts your change depends on.

This is the standard pattern in `hermes-agent` — see `tests/gateway/test_35809_auto_reset_clean_context.py`
(`_find_compression_exhausted_reset_block()`), which pins that the auto-reset block captures
`reset_session(...)` and calls `_sync_telegram_topic_binding`. Mirror it.

## The recipe

1. **Extract the testable logic into a pure helper** first if you can — a `_reset_reason_text(reason,
   policy) -> str` that depends only on its args, unit-tested directly. That covers the *behavior*.
   The AST pin then only has to guard the *wiring* (that the handler calls the helper, sends
   out-of-band, logs the marker), not re-test the behavior. Prefer this split: pure-helper unit tests +
   a thin AST wiring pin beats one big AST blob.

2. **Locate the block by a string constant in its `if`-test, then disambiguate by the calls it
   contains** (a bare "find an `if`" matches dozens):

```python
import ast, inspect
from gateway import run as gateway_run

def _find_block() -> ast.If:
    tree = ast.parse(inspect.getsource(gateway_run))
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        consts = {n.value for n in ast.walk(node.test)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if "was_auto_reset" in consts:                       # the block's signature literal
            calls = {s.func.attr for s in ast.walk(node)
                     if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)}
            if "_reset_reason_text" in calls or "send" in calls:   # disambiguate
                candidates.append(node)
    assert candidates, "block not found — structure changed or walker stale"
    return max(candidates, key=lambda n: len(list(ast.walk(n))))   # outermost match
```

3. **Assert the load-bearing structural facts** — what your change relies on, stated as invariants a
   future refactor must preserve:

```python
# uses the helper (mode-correct wording) and sends out-of-band
attrs = {s.func.attr for s in ast.walk(block) if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute)}
names = {s.func.id  for s in ast.walk(block) if isinstance(s, ast.Call) and isinstance(s.func, ast.Name)}
assert "_reset_reason_text" in names and "send" in attrs

# the lost-send path logs the greppable WARNING marker (not a silent debug)
assert any(isinstance(n, ast.Name) and n.id == "SESSION_RESET_NOTICE_SEND_FAILED" for n in ast.walk(block))
assert any(isinstance(s, ast.Call) and getattr(s.func, "attr", "") == "warning" for s in ast.walk(block))

# INVARIANT: the message is out-of-band — never appended into model history (prompt-cache / role-alternation safety)
bad = [s for s in ast.walk(block)
       if isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) and s.func.attr == "append"
       and isinstance(s.func.value, ast.Name) and s.func.value.id in {"messages", "history"}]
assert not bad, "notice must not mutate messages/history"
```

The `messages/history.append` negative pin is especially valuable: it's a *cache-safety invariant*
(SOUL: prompt caching is sacred) expressed as a test that a future edit can't silently violate.

## Pair it with an out-of-process invariant check too

An AST pin proves the *source shape*; pair it with a cheap runtime check of the *behavioral
invariant the shape protects*. Example from this session: verify the `was_auto_reset = False` clear
sits OUTSIDE the `try/except` (so the send is attempted exactly once per event, no throttle needed) —
walk the block's `ast.Try` nodes and assert the clearing `ast.Assign`'s `lineno` is not inside any
`Try` body. That turns "I think it's once-per-event" into a pinned fact.

## RED-prove the pin (and any new gate) has teeth

An AST pin or a new behavioral test is only worth keeping if it FAILS when the thing it guards
regresses. Mutation-prove it in-place, cleanly:

```python
# temporarily revert the gate/wiring to the pre-fix form, run ONLY the new test, assert it FAILS, restore.
# (do it via a backup-restore of the file, then re-run — see references/git-verify-on-clean-tree.md
#  for the bytecode-cache caveat: clear __pycache__ if a restored file still reads mutated.)
```

This session the `had_any_turn` gate fix was RED-proven exactly this way: revert
`had_any_turn or last_prompt_tokens > 0` back to `last_prompt_tokens > 0` → the compressed-then-idle
test failed → restore → passed. A test that never goes red proves nothing.

## Don't over-pin

The AST pin should assert the **handful** of facts your change depends on, not freeze the whole block's
shape (that's a change-detector test — the AGENTS doc rejects those). Pin: "calls the helper," "sends
out-of-band," "logs the marker," "doesn't mutate history." Don't pin: exact variable names, statement
order, the wording string (that's the helper's unit test's job).

# Test Isolation: Frozen-State Leaks & the Leak-Probe Verification Pattern

When a pytest suite passes in isolation and with `-p no:randomly` but fails
~1-in-N full-suite runs (order-dependent flakiness), the cause is almost always
**global state mutated in one test bleeding into a later one**. The classic
trap: mutating a *frozen* dataclass.

## The frozen-dataclass / monkeypatch-bypass trap

`monkeypatch.setattr(obj, name, value)` records the original and auto-restores
it on teardown — that's the whole point of `monkeypatch`. But on a
`@dataclass(frozen=True)` instance, `monkeypatch.setattr` raises
`FrozenInstanceError`. Tests then fall back to:

```python
object.__setattr__(portal.settings, "portal_hostnames", {"blocked.local.ace"})
```

`object.__setattr__` writes the attribute **but registers no teardown**. The
mutation persists into every subsequent test in the process. If the value
matters to assertions elsewhere (e.g. a hostname set checked by SNI / host-guard
logic), those tests flip pass/fail depending on collection order.

Real case (dns-block-portal, 2026-06): six call sites across five test files
wrote `portal_hostnames` / `blocked_domain_log_path` on a frozen `Settings`
via `object.__setattr__`. `test_device_scoped_catchup.py` failed ~1-in-3 full
runs; isolation and `-p no:randomly` were always green — the tell-tale signature.

## Why `-p no:randomly` "fixing" it is a red herring

`-p no:randomly` (or any fixed order) hides the bleed by putting the leaking
test after the tests it would corrupt. The suite is still broken — it's just
lucky. Don't ship `-p no:randomly` as the "fix"; fix the leak.

## The fix: autouse snapshot/restore for frozen instances

Per-call-site `frozen_setattr` helpers work but require touching every fixture.
The bulletproof, zero-churn fix is an **autouse conftest fixture** that snapshots
the whole instance's `__dict__` before each test and restores it after — covering
all current leaks *and any future one*, regardless of which attribute or file.

```python
# tests/conftest.py
import copy
import pytest

def _live_settings():
    from app import main as portal   # lazy: don't depend on import order
    return portal.settings

@pytest.fixture(autouse=True)
def _isolate_settings():
    settings = _live_settings()
    saved = {k: copy.copy(v) for k, v in vars(settings).items()}
    saved_keys = set(saved)
    yield
    current_keys = set(vars(settings))
    for key in current_keys - saved_keys:        # attrs added during the test
        object.__delattr__(settings, key)
    for key, value in saved.items():             # restore originals
        object.__setattr__(settings, key, value)
```

Notes:
- `copy.copy` each value so a test mutating a set/list *in place* (not
  reassigning) still gets a clean original restored.
- Restore via `object.__setattr__` — the same channel that bypasses frozen, so
  it actually writes back.
- Handle keys added during the test (`current - saved`) by deleting them.
- Keep `_live_settings` a lazy import so conftest collection doesn't couple to
  module import order.
- Also ship an opt-in `frozen_setattr` fixture for tests that prefer explicit
  per-attribute control; the autouse net catches everything else.

## Verifying the fix actually isolates (the leak-probe pattern)

A green suite does NOT prove your isolation fixture engages — it might be a
no-op while the flakiness was just lucky that run. Prove it with a **two-test
leak probe** placed *inside the test tree* (so conftest applies):

```python
# tests/test_leak_probe_tmp.py   (temporary, delete after)
from app import main as portal

def test_aaa_mutate_then_leak():
    object.__setattr__(portal.settings, "portal_hostnames", {"leaked.invalid"})
    assert portal.settings.portal_hostnames == {"leaked.invalid"}

def test_zzz_sees_restored_value():
    # If isolation works, the leak from test_aaa must be gone.
    assert "leaked.invalid" not in portal.settings.portal_hostnames
```

- `aaa`/`zzz` naming forces ordering so the mutator runs first.
- Both pass ⇒ fixture genuinely restores. Run it, then delete the probe file.

### Pitfall: the probe MUST live under `tests/`

`tests/conftest.py` only applies to tests collected under that directory. A
probe dropped in `/tmp` (or pointed at a foreign `--rootdir`) won't pick up the
autouse fixture and will *correctly fail* — which looks like the fix is broken
when it isn't. If the probe fails, first confirm it's actually inside the tree
the conftest governs before doubting the fixture. (Seeing the `/tmp` version
fail and the `tests/` version pass is itself good confirmation the conftest is
what's doing the work.)

## Confidence bar for "deterministic now"

Order-dependent flakiness is nondeterministic, so one green run proves nothing.
Run the full suite **5+ consecutive times** and require identical green counts
(e.g. `614 passed, 49 skipped` each), *plus* the leak probe. Single-run "passed"
is not evidence for a flakiness fix.

## Generalizes beyond frozen dataclasses

Any global/module-level mutable state written without auto-teardown is the same
bug class: module singletons, class attributes, `os.environ` set without
`monkeypatch.setenv`, registries, caches, `logging` config. The autouse
snapshot/restore pattern applies to any of them — snapshot the container before,
restore after. The signature is always: **green in isolation + green with fixed
order + flaky in full random-order runs.**

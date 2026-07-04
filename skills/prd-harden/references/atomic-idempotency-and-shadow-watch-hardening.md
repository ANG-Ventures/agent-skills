# Atomic idempotency + shadow-watch hardening

Use this reference when hardening staged/shadow systems, watcher crons, audit logs, provenance logs, or any code where repeated runs should be safe.

## Class of bug

A common fake-idempotency pattern is:

1. check whether an artifact/log/marker exists;
2. if absent, append durable side effects;
3. write the artifact/marker.

That is a TOCTOU race. Concurrent runs can all observe "absent" before any process writes the marker, then all append the side effect. This is especially dangerous for evidence logs (`saw-didn't-save`, audit artifacts, promotion gates) because double-counting can make a staged system look safer or more mature than it is.

## Hardened pattern

Use an **atomic claim** before any durable side effect:

- choose a deterministic per-run claim path, keyed by the real run identity (`brief + run_ts`, job id, source id, etc.);
- create it with exclusive-create semantics (`open(..., 'x')` in Python, `writeFileSync(path, data, { flag: 'wx' })` in Node, or equivalent `O_CREAT|O_EXCL`);
- only the claim winner may write durable side effects (provenance append, audit log, final artifact, notification marker);
- losers may recompute and print diagnostics, but must not mutate durable state;
- write the final artifact by overwriting the placeholder after side effects complete, or keep a separate `.claim` file if partial artifacts are unacceptable.

## Required adversarial tests

Add tests that would fail under the racy check-then-act implementation:

1. **Concurrent same-run test:** launch N subprocesses against the same run identity and assert the durable side effect appears exactly once.
2. **Sequential re-run test:** run the same command twice and assert no double-append.
3. **Malformed/corrupt artifact test:** a corrupt artifact should be skipped or reported without breaking aggregation.
4. **Dry-run side-effect test:** snapshot the runtime state before/after `--dry-run` and assert byte-identical state.

RED-prove the concurrency test when practical: temporarily revert the atomic claim to a stat/existence check and verify the test fails with N× duplicated side effects. Restore immediately.

## Hermetic testability

Do not let tests write into real `~/.hermes` state. Make artifact/provenance directories env-overridable, e.g.:

- `OUTPUT_SHADOW_ARTIFACT_DIR`
- `OUTPUT_SHADOW_PROVENANCE_DIR`

Subprocess-driven tests can then exercise the real CLI path while writing only under a temp directory.

## Read-modify-write LEDGER variant: `fcntl.flock` + per-writer `mkstemp` (2026-06-22)

The atomic-claim pattern above guards an *append*. A different shape is a **read-modify-write
JSON ledger** (an in-flight registry: read the dict → mutate one key → write the whole file back).
Two concurrent `record`/`clear`/`sweep` operations on such a ledger race in TWO ways, and a green
happy-path suite is structurally blind to both because the unit tests call the functions
sequentially:

1. **Lost update** — both read the old dict, both write back their single change, the second
   clobbers the first. N concurrent inserts → far fewer than N survive.
2. **Crash on a shared temp name** — the "atomic" `tmp = PATH + ".tmp"; write tmp; os.replace(tmp,
   PATH)` pattern uses ONE fixed `.tmp` path, so two writers collide: one's `os.replace` raises
   `FileNotFoundError` because the other already renamed the shared tmp out from under it.

Found 2026-06-22 in a kill-switch in-flight ledger: 20 concurrent `record_arm` calls **crashed**
and left the ledger holding **0 of 20** entries — which would have defeated the "emergency stop
actually un-arms every in-flight item" guarantee (the sweep reads an empty/corrupt ledger and finds
nothing to un-arm). This is the safety-critical version: the concurrency bug doesn't just lose data,
it **silently disables a recovery mechanism**.

**Fix (two parts, both needed):**
- **Serialize the read-modify-write with an advisory file lock.** A small `_Lock` context manager
  over `fcntl.flock(open(PATH + ".lock", "w").fileno(), LOCK_EX)` wrapping every public
  read/mutate function makes the whole RMW atomic w.r.t. other processes/threads. (Cross-process,
  unlike a `threading.Lock`.)
- **Unique temp file per writer:** `fd, tmp = tempfile.mkstemp(dir=os.path.dirname(PATH),
  suffix=".tmp")` instead of a shared `PATH + ".tmp"`, with cleanup-on-error (`os.unlink(tmp)` in an
  `except`). Even under the lock this is the correct atomic-swap hygiene; without the lock it stops
  the crash but not the lost update.

**RED-prove it:** spawn 20 real threads each inserting a distinct key, assert all 20 survive; then
20 concurrent deletes, assert the ledger empties. Revert the lock (make `_Lock` a no-op) and watch
the count come back wrong (held 2/20 in the repro) — that's the teeth. macOS note: `fcntl.flock`
works; there is no `flock` on Windows (use `msvcrt.locking` or a portable lib if cross-platform).

## DUPLICATE DIVERGED IMPLEMENTATIONS — the multi-session fork the lint pass surfaces (2026-06-22)

A real hardening-pass discovery that is NOT a test bug: **two files implementing the same component,
built in different sessions, that DIVERGED.** One carried a safety invariant the other lacked; the
other carried operational surface (CLI/reconcile/status) the first lacked; both had their own green
test suite, so neither suite revealed the split. This is the "fix the wrong copy" trap
(`prd-closeout` warns about it for scripts-with-multiple-copies) at the module level.

How it surfaces and what to do:
- **The tell is almost never a failing test** — it's the **ruff/lint pass** flagging an issue in a
  file you didn't think existed (`greploop_actuator.py` vs `actuator.py`), or a `grep` for the
  subsystem term returning two hits. Run `ls`/`grep` for sibling names of every module you touched.
- **Don't just delete the older one — RECONCILE.** Diff their capabilities (`grep -nE "^def "` each).
  Decide which is canonical (usually the one with the richer operational surface AND the one the
  SKILL.md / callers reference), then **fold the unique value of the other into it** (here: port the
  `protection_ok` B2 invariant into the canonical actuator), port its best tests, and **archive**
  the redundant pair to `.archive/` (don't hard-delete — recoverable).
- **Verify the canonical one is what's referenced everywhere** after: `grep -rn <old-module-name>`
  the SKILL.md + docs + crons and repoint them. A stale `scripts/<old>.py` reference in the skill is
  a future "fix the wrong copy" incident waiting to happen.

## Closeout reporting

If a report needs to mention commits, avoid a self-referential amend loop. A commit cannot accurately contain its own final SHA if you keep amending it. Prefer:

- "report introduced in `<sha>`; follow-up commits may correct report text"; or
- "current HEAD when read"; or
- put final SHA in the chat summary, not inside the committed report.

## Where this came from

Wave 6 P1 of `siftly-ace` found the append-TOCTOU bug in an output-shadow provenance logger. The original artifact-exists `statSync` guard let concurrent shadow runs append duplicate surfaced-provenance, inflating the saw-didn't-save evidence used by a later promotion gate. The fix was an atomic O_EXCL artifact claim plus RED-proven subprocess tests. The `fcntl.flock` ledger variant + the duplicate-diverged-implementation reconciliation came from hardening the greploop merge actuator/kill-switch (2026-06-22).

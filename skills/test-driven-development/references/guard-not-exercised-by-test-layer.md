# The "green with AND without the fix" trap — your test layer can't reach the guard

RED-GREEN's whole point is that the test fails *because the feature is missing*. But there's a
sneakier failure that passes the letter of RED-GREEN while violating its spirit: a test that goes
**green even when you delete the fix**, because the test exercises the wrong *layer* and never reaches
the guard at all. A weak test masquerading as a real gate is worse than no test — it ships false
assurance and a future refactor silently removes the protection.

## The episode (native_content_slimmer RC#3, single-flight GC lock, 2026-06-15)
The fix: in `_run_gc_async`, skip spawning a GC thread if one is already alive (prevent daemon-thread
fan-out). First test drove it **end-to-end** through `transform_tool_result(...)` twice while a GC was
blocked, then asserted `len(alive) == 1`. It passed. Good? No — when I **deleted the guard and re-ran,
it STILL passed**. The full write path is gated *upstream* by the B1 over-cap / health check, so the
second `transform_tool_result` never actually reached `_run_gc_async` to spawn a second thread. The
test proved nothing about the guard; it proved the upstream gate happens to suppress the second write.

The fix to the test: drop to the **layer the guard lives at**. Call `_run_gc_async(...)` *directly*
with `_run_gc` monkeypatched to a blocking stub, invoke it 3×, assert exactly one live thread. Now
removing the guard → 3 threads → test fails (real RED); restoring → 1 thread → green.

## The rule (do this for every guard/branch test)
**After you see GREEN, delete the fix and re-run. If the test still passes, the test is testing the
wrong layer — rewrite it closer to the guard.** This is the fail-before check done *honestly*: it's
not enough to see *a* red once; you must confirm the red is caused by the *absence of your specific
guard*, not by some unrelated upstream condition that also happens to short-circuit the path.

- Prefer a **unit test at the function the guard lives in** over an end-to-end test, when the guard is
  one branch deep inside a pipeline that has earlier gates (over-cap checks, auth, validation, early
  returns). End-to-end can't isolate which gate fired.
- Monkeypatch the *slow/blocking* collaborator (here `_run_gc`) so you can hold the precondition open
  and observe the guard's effect deterministically — no sleeps, no races.
- The tell you got this wrong: your "fail-before" experiment fails for a *different reason* than the
  bug, or (worse) doesn't fail at all.

## Companion trap: `git checkout <file>` silently reverts an UNCOMMITTED fix
While doing the delete-the-fix experiment, I used `git checkout hook.py` to "restore" after a temp
edit — but my actual guard fix was **still uncommitted**, so `git checkout` wiped it too. The suite
then "failed after restore" and I briefly thought the fix was wrong; really the fix was gone. 
**Commit (or stash) the fix before running any `git checkout`-based fail-before experiment**, or do
the temp-removal with an in-memory string edit you re-apply via the editor, never via `git checkout`.
A clean `git status` after `checkout` means you're back at HEAD — which does NOT contain your
uncommitted work.

# IndexedDB test hangs: a cached open connection blocks `deleteDatabase`

**Class:** test-infra pitfall for any IndexedDB-backed module (op-logs, caches, offline
stores) where tests reset the DB between cases. Instrument-before-theorize in action.

## The symptom that names the cause

First run of a vitest/jest suite against an IDB module (real or `fake-indexeddb`):
- the **first** test times out at exactly the default test timeout (5000ms), and
- **every subsequent** test fails in the `beforeEach`/`beforeAll` **hook** at the hook
  timeout (10000ms),
- total suite duration ~55s of pure hangs (N hooks × 10s).

The shape — *first test reaches the test wall, the rest hang in the reset hook* — is the
tell. It is NOT "the logic is broken"; it's the **DB-lifecycle in the test harness**.

## Root cause

A module that caches its connection (`let dbPromise; openDb() { if (dbPromise) return
dbPromise; ... }`) leaves the IDB connection **open**. The `beforeEach` then calls
`indexedDB.deleteDatabase(name)` to get a clean DB — but **an open connection blocks
`deleteDatabase`** (it fires `onblocked` and never `onsuccess`). The reset never
completes, so the hook hangs. A bare `dbPromise = null` cache-drop does NOT help: it
clears the JS reference but leaves the underlying IDB connection open.

## Instrument before theorizing (the cheap probe that split logic-vs-harness)

Before touching the module, prove whether the *logic* works at all in isolation — a
~10-line `tsx`/`node` script that imports the module, does one append + one read,
prints a sentinel, and `process.exit(0)`:

```
PROBE_OK seq=1 count=1   # in <2s
```

A fast PROBE_OK means the persistence logic is correct and the failure is purely the
test harness's DB reset — so you fix the teardown, not the module's core. (This is the
"source-code reasoning lies where empirical observation is cheapest" rule applied to a
test hang: don't read the oplog code for a bug; run it once and watch it pass.)

## Fix

1. Add an **async `closeDb()`** to the module that actually closes the live connection
   before dropping the cache:
   ```ts
   export async function closeDb(): Promise<void> {
     if (!dbPromise) return;
     try { (await dbPromise).close(); } catch { /* ignore */ }
     dbPromise = null;
   }
   ```
2. `beforeEach` does **`await closeDb()` BEFORE `deleteDatabase`** (and resolve the
   delete promise on `onsuccess`/`onerror`/`onblocked` so a still-blocked delete can't
   wedge the hook either):
   ```ts
   beforeEach(async () => {
     await closeDb();
     await new Promise<void>((res) => {
       const r = indexedDB.deleteDatabase("dbname");
       r.onsuccess = r.onerror = r.onblocked = () => res();
     });
   });
   ```
3. Bonus: `closeDb()` is the honest "simulate a torn-down + respawned SW" primitive for
   a *durability/persistence* test (close the connection, reopen, assert prior writes
   are still there) — better than a cache-drop, which never modelled a real restart.

Result this session: 55s of hangs → 271ms, 36→37 tests green. The `closeDb()` helper is
also genuinely needed in production (restore-into-fresh-store must close before swap), so
the test bug surfaced a real API gap rather than a test-only hack.

## Generalization

Any store with a cached singleton connection that tests want to wipe between cases:
export a real `close()`, call it before `deleteDatabase`, and resolve the delete on
*all three* outcomes (`onsuccess`/`onerror`/`onblocked`). The same lock-holder logic
applies to IDB **version upgrades** — an open connection blocks `onupgradeneeded` too.

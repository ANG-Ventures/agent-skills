# Route-handler & read-through-cache hardening patterns

Two concrete patterns proven on the siftly-ace Wave 5 hardening pass (2026-06-09). Both are
the "harden the integration boundary, not just the pure decision" case from rule 2.

---

## 1. Route-level handler test with mocked boundaries (prove the WIRING)

A pure decision helper (e.g. `resolveProvider(preferred, availability)`) can be 100% unit-tested
and still ship a bug, because the bug is in *how the route wires it up* — does the handler actually
probe live key presence? does it short-circuit the expensive/dangerous fallback? A unit test of the
pure function can't see that. Drive the **real exported handler** with mocked boundaries.

**Pattern (Next.js route + vitest):**

- `vi.mock(...)` every boundary BEFORE importing the route: the DB (`@/lib/db` prisma), the SDK
  client factory, and especially the **expensive/dangerous fallback** (the CLI/agentic path) so you
  can assert it is *never called* on the hardened paths.
- Drive the real `POST` with a `new Request(...)` cast to the handler's param type.
- Assert behavior the unit test can't: resolved provider passed to the client factory, **`expect(cliFn).not.toHaveBeenCalled()`** on the no-hang paths, fast status codes, error body names the provider/model.

```ts
// mock boundaries first
vi.mock('@/lib/db', () => ({ default: { setting: { findUnique: vi.fn(/* DB-keyed map */) }, /* … */ } }))
const codexPrompt = vi.fn(/* … */)       // the 90s agentic path — spy so we can prove it's untouched
vi.mock('@/lib/codex-cli', () => ({ codexPrompt: (...a: unknown[]) => codexPrompt(...a), /* … */ }))
import { POST } from '@/app/api/search/ai/route'

it('preferred=anthropic, only OPENAI key present -> OpenAI SDK, 200, CLI NEVER called', async () => {
  settingValues.set('aiProvider', 'anthropic'); process.env.OPENAI_API_KEY = 'fake'
  const res = await POST(makeRequest({ query: 'q1' }))
  expect(res.status).toBe(200)
  expect(resolveAIClientForProvider).toHaveBeenCalledWith('openai', expect.anything())
  expect(codexPrompt).not.toHaveBeenCalled()   // the hardening guarantee
})
```

**Gotchas:**
- **In-process caches leak across tests.** The route had a module-level `searchCache` keyed by query.
  Test A cached query `"X"`; Test B reusing `"X"` hit the cache and skipped resolution entirely →
  false failure. **Give every test a unique query/key** (or clear the cache in `beforeEach`). This is
  also how you *prove* the test really exercises the path: when the collision made the db-preferred
  test go red, that was RED confirming the test bites.
- **`vi.fn()` spread args trip tsc** (`TS2556: A spread argument must either have a tuple type…`).
  The mock wrapper `(...args: unknown[]) => fn(...args)` fails because `fn` (a `vi.fn()`) has no
  call signature. Cast at the call site: `(fn as (...a: unknown[]) => unknown)(...args)`.
- **Restore env in `afterEach`** — save/delete the provider env keys in `beforeEach`, restore in
  `afterEach`, so tests don't leak `OPENAI_API_KEY` into each other or the rest of the suite.
- **Fake key literals**: use an obviously-fake token (`'fake-token'`), never a realistic
  `sk-…` string, so the secret scanner at commit doesn't flag the test file.

---

## 2. Read-through cache: the invariants worth testing

A read-through cache (first call/window pays, subsequent calls within TTL are free) has a small set
of failure modes that unit tests must lock. Proven on the x-feed timeline + interest-search caches.

| Invariant | Test |
|---|---|
| Cold MISS fetches + writes the cache file | assert status `miss`, fetch called N times, cache file exists |
| Warm HIT within TTL costs **0 reads** | assert status `hit`, **`fetch.not.toHaveBeenCalled()`**, same data returned |
| Stale (past TTL) re-fetches | advance `now` past TTL → status `miss`, fetch called again |
| **Key-set change invalidates** (the safety one) | change one input (a query, a window) → different cache key → MISS, NOT stale wrong-data. Key = hash of the *sorted* input set so order doesn't matter. |
| Day-boundary key | cache keyed by the **logical day in the cron's own timezone** (PT here), not UTC — an evening rerun must not key tomorrow's file; next morning is a guaranteed fresh MISS |
| Errors never poison the cache | upstream throws (402/timeout) → the fetch rejects and **nothing is written**; assert `readCache(...)` is null after a failed run |
| `--force` / `--no-cache` escape hatches | force → fresh fetch but still writes; no-cache → fresh fetch, no file written |
| `isFresh` boundary | exactly-at-TTL is stale, just-under is fresh (off-by-one lock) |

**Design rules that make the above clean:**
- Make the cache module **pure** (inject `fetch`, inject `now`, inject `cacheDir`) so every invariant
  is a deterministic unit test with no network and no clock dependence. The thin CLI wrapper supplies
  the real `xurl`/`fetch` + real `Date` and is the only part that needs a live smoke test.
- **Day key in the consumer's timezone.** Using UTC was a latent bug on the timeline cache: an evening
  PT rerun crosses into the next UTC day and keys a stale file under tomorrow's name. Use
  `Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' })` → `YYYY-MM-DD`.
- **Snowflake / numeric IDs compare as BigInt**, not string length-then-lex, so ordering/merge stays
  correct across digit-length changes. The discriminating test is a leading-zero cross-length case
  (`'000…001'` 20ch =1 vs a 19-char id) that length-lex gets wrong and BigInt gets right — a naive
  decimal test passes under *both* and is non-discriminating.
- **Cache key = stable hash of the sorted input set.** Then editing the inputs (queries, window) can
  never serve stale results for a different request — it just misses and re-fetches.

**Live smoke proof (after the unit invariants):** run the real CLI twice — Run 1 cold MISS (real
reads), Run 2 warm HIT (0 reads, same data) — then `--force` (real reads again). Three runs, ~30s,
proves the seam end-to-end without trusting the unit mocks.

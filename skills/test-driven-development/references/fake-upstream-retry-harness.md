# Testing a retry/dispatch wrapper with an injected fake-upstream seam

For Node HTTP proxies/gateways that expose a `requestImpl` (or `httpRequest`)
injection seam, you can test retry/backoff/disconnect behavior with **zero live
API** by injecting a fake upstream that returns scripted responses per attempt.
This pattern works, but two specific footguns will deadlock or hang the test
runner and cost many debug iterations. Both bit a real session
(claude-api-proxy v2.15.0 bounded-retry build) — encode them so you don't repeat.

## The pattern (works)

A fake `requestImpl(options, callback)` returns a writable req stream; after the
proxy calls `.write(body); .end()`, you invoke the proxy's response `callback`
with a synthetic `upRes` (a `PassThrough` carrying `statusCode`/`headers`/body).
A per-attempt `script(attempt, captured)` lets you return "N×429 then 200".

```js
function fakeUpstream(script) {
  const calls = [];
  let dispatched = 0;                         // PITFALL 1: synchronous counter
  const requestImpl = (options, callback) => {
    const attempt = dispatched++;             // read at call-time, NOT in .then
    const reqStream = new PassThrough();
    const chunks = [];
    reqStream.on('data', (c) => chunks.push(Buffer.from(c)));
    let aborted = false;                        // PITFALL 2: detect real abort
    reqStream.on('close', () => { if (!reqStream.writableFinished) aborted = true; });
    const origEnd = reqStream.end.bind(reqStream);
    reqStream.end = (chunk, enc, cb) => {
      origEnd(chunk, enc, cb);
      Promise.resolve().then(async () => {
        calls.push({ options, headers: options.headers,
          body: Buffer.concat(chunks).toString('utf8'),
          get aborted() { return aborted; } });
        const r = script(attempt, calls.at(-1)) || {};
        if (r.delayMs) await new Promise((res) => setTimeout(res, r.delayMs));
        if (aborted) return;                    // client gave up; never deliver
        const upRes = new PassThrough();
        upRes.statusCode = r.status ?? 200;
        upRes.headers = r.headers ?? { 'content-type': 'application/json' };
        callback(upRes);
        if (r.body != null) upRes.write(r.body);
        upRes.end();
      });
    };
    return reqStream;
  };
  return { requestImpl, calls };
}
```

## PITFALL 1 — Race: compute `attempt` synchronously, not in the async `.then`

If you read `const attempt = calls.length` and only `calls.push(...)` later inside
the `.then()` microtask, a fast retry (`setTimeout(dispatchOnce, 0)` after a
near-zero jitter) can re-enter `requestImpl` BEFORE the prior attempt's `.then`
pushed — so attempt reads `0` again and your "N×429 then 200" script loops
forever at attempt 0/1 and the client request never resolves. **Fix:** a
synchronous `let dispatched = 0; const attempt = dispatched++;` at call-time.

Symptom: test logs show `retry 1/5` then stall; the wrapper works in a
standalone script but hangs only under `node --test`.

## PITFALL 2 — Deadlock: do NOT override `.destroy` or read native `.destroyed`

To detect a client-disconnect (so the fake doesn't deliver a response the proxy
no longer wants), the tempting move is to override `reqStream.destroy` or check
`reqStream.destroyed`. Both are wrong:

- **Overriding `.destroy`** breaks the `PassThrough` write/end lifecycle and
  **deadlocks** `upstream.write(body); upstream.end()` — the second attempt's
  callback never fires.
- **Reading native `.destroyed`** false-positives: a `PassThrough` naturally
  closes (and sets `.destroyed = true`) after `end()` + drain, with NO client
  disconnect. Your fake then skips delivery on every retry and the request hangs.

**Fix:** detect a *real* abort via `reqStream.on('close', () => { if
(!reqStream.writableFinished) aborted = true; })`. A clean end-of-stream close
has `writableFinished === true`; only a proxy-initiated `upstream.destroy()` mid
-flight leaves it false. Read that `aborted` flag, never `.destroyed`.

## PITFALL 3 — `server.close()` hangs the runner on keep-alive sockets

In `t.after`, `server.close()` waits for keep-alive client sockets to drain and
can hang the whole test file. Force them shut:

```js
t.after(() => new Promise((resolve) => {
  if (server.closeAllConnections) server.closeAllConnections();
  server.close(() => resolve());
}));
```

## Debugging discipline when a node:test file hangs but standalone works

The wrapper logic is almost never the bug — the harness is. Bisect fast:
1. Reproduce the exact flow in a standalone `node script.js` with `process.exit`.
   If it passes, the bug is in the test harness (cleanup, race, or stream
   lifecycle), not the production code.
2. Instrument the fake (`console.error` the attempt #, the `aborted`/`destroyed`
   flag, and stream `'close'`) to see which attempt stalls and why.
3. Run ONE test at a time with `--test-name-pattern` + `--test-force-exit` and a
   shell `timeout` so a hang becomes a fast, inspectable failure.

## What this proves without a live API

rides-out-transient (N×429→200, client sees 200, N+1 upstream calls);
gives-up-bounded; quota-cap-not-retried (failover signal preserved);
permanent-4xx-not-retried; client-disconnect cancels pending retry AND destroys
in-flight upstream; per-attempt header mutation (retry-count increments,
session-id stable); retry-after honored past budget. All from the seam, no
network.

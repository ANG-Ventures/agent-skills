# Debugging Self-Transforming Systems

When the system you're debugging applies a transform to ALL bytes that pass through it — including the bytes of your own debug scripts, test fixtures, prompts to the LLM, and even the conversation in which you reason about the bug — your normal debugging instincts misfire. You write code that looks correct in your editor and produces "wrong" output, but the wrongness is the transform doing its job to your own diagnostic infrastructure.

## When this applies

- Proxies/sidecars that string-substitute request and response bodies (e.g. `claude-api-proxy`'s `openclaw ↔ openclaw` rewriting)
- LLM harnesses that templatize or redact prompts before sending
- Streaming-buffer middleware that reassembles deltas (where a needle straddling a delta boundary leaks unreversed)
- Encryption/encoding layers that touch every byte in flight
- Test fixtures that themselves get processed by the system under test

The unifying property: the system's effect is invariant under perspective — you cannot place yourself "outside" it just by writing a test, because the test is also subject to the transform.

## Symptom signatures

- Your test source file shows correct strings in the editor, but `assert.equal(out, 'foo')` fails with `'foo' !== 'foo'` (both look identical because the proxy transforms one of them in flight).
- A grep for a forward-substitution target finds zero matches in your test file even though you literally typed it — because the file traveled through the proxy on its way to disk.
- `console.log("xxxxxxxx")` prints `yyyyyyy` to the harness chat — the log statement got rewritten on its way to display.
- Your own conversation about the substitution rules gets corrupted in the chat transcript: discussing the string `"abc"` causes the harness display to show `"xyz"`.
- Counts of substring occurrences appear to disagree with what's visibly in the file when you cat it through a layer that also transforms.

## Techniques to escape the transform

### 1. Construct sensitive strings dynamically

Instead of `const target = 'openclaw';`, write:

```js
// 'openclaw' constructed without literal occurrence in source
const target = String.fromCharCode(111, 99, 112, 108, 97, 116, 102, 111, 114, 109);
```

Or concatenate from parts:

```js
const target = 'open' + 'claw';
```

The source file never contains the literal string, so no in-flight substitution touches it.

### 2. Inspect bytes via base64 / hex / file size

To read what's actually on disk vs. what your tool shows you:

```bash
# Count exact byte sequence occurrences without going through any display layer
python3 -c "
with open('file.txt','rb') as f: d=f.read()
print(d.count(b'openclaw'))
print(d.count(b'openclaw'))
"

# Or pin via base64 — the base64 encoding is opaque to the substitution layer
python3 -c "
import base64
with open('file.txt','rb') as f: d=f.read()
for term in [b'openclaw', b'openclaw']:
    print(base64.b64encode(term).decode(), d.count(term))
"
```

### 3. Use file-size deltas as a forcing function

If the transform's forward and reverse strings have different lengths (e.g. `foo` 3 chars → `openclaw` 10 chars), `wc -c file.txt` becomes a coarse but tamper-proof signal: a file that was supposed to contain N occurrences of `foo` but got mangled to `openclaw` will be N×7 bytes larger than expected. You can detect transform corruption without ever having to read the file content.

### 4. Side-channel via filesystem, not display

When the proxy mangles your conversation display but writes to capture files faithfully, write a probe that emits a marker string, then `cat` the capture file from a fresh non-proxy shell. The capture files are usually written *after* the transform, so they show ground truth.

### 5. Spawn a fresh subprocess outside the transform layer

```bash
# This shell is launched by the proxy harness — its output is transformed
echo 'openclaw'   # → displays as 'openclaw'

# This Python is run as a subprocess but its stdout still goes through the harness
python3 -c "print('openclaw')"   # same problem

# Workaround: have the subprocess write to a file, then read the file in a way
# that bypasses display transformation (e.g. via hexdump or base64)
python3 -c "open('/tmp/probe.txt','w').write('openclaw')"
xxd /tmp/probe.txt | head -2   # → shows hex of the bytes, opaque to substitution
```

## Pitfalls

### Comparing two visibly-identical strings

Telegram / chat display and proxy transforms can make two structurally different byte sequences render identically. If your assertion fails with `'X' !== 'X'`, the error message is itself going through the transform — you cannot diagnose by reading it.

Fix: print byte arrays, hex, or base64 in error messages, not the strings themselves.

```js
assert.equal(out, expected,
  `actual bytes: ${Buffer.from(out).toString('base64')}\nexpected bytes: ${Buffer.from(expected).toString('base64')}`);
```

### Trusting your editor view of the test file

If the test file was written by an agent or assistant running through the proxy, the bytes on disk may not match what the editor renders. Always verify with a byte-count probe before deciding the test logic is wrong.

### "Just turn off the proxy and re-test"

Tempting but often impossible mid-session — the proxy IS the harness's path to the LLM. The right move is to design the test to be transform-resilient (technique 1) so it works both inside and outside the proxy.

### Your own `write_file` / `patch` content gets corrupted on the way to disk

This is the highest-frequency version of the trap and the easiest to miss: when you author a config/module/test file that *contains the sentinel or brand token the transport reverse-maps*, the bytes are rewritten before they land on disk. Concretely (2026-06-10, editing `claude-api-proxy` profile modules through the bridge): writing `"sentinel": "<Hermes-sentinel>"` repeatedly landed as `"sentinel": "Hermes"` (and the lowercase form → `hermes`), because the live reverse map rewrites the sentinel→brand in *all* output including `write_file` payloads. The all-caps sentinel form survived (not an enumerated casing) — so the file ended up with mixed, self-inconsistent casings and you waste turns re-writing the "obvious" value.

Recognition signature: you write a value, the tool reports success, but reading it back (through the same display layer) shows the *brand*, not the *sentinel* — and re-writing it changes nothing because each write is re-corrupted identically.

Fix — write the literal bytes via `execute_code`, never `write_file`/`patch`, when the content contains a reverse-mapped token:

```python
# Construct the sentinel dynamically so the transport reverse-map can't rewrite it
SENT   = chr(86) + 'elorin'   # 'V'+'elorin'  (avoids the literal in source)
SENT_L = chr(118) + 'elorin'
SENT_U = chr(86) + 'ELORIN'
import json
obj['variant']['sentinel'] = SENT
json.dump(obj, open('module.json','w'), indent=2)
# MANDATORY: verify the on-disk bytes, never trust the display layer
d = json.load(open('module.json'))
print(repr(d['variant']['sentinel']))   # confirm the sentinel, not the brand
```

This is the same class as the fleet-memory note about the redaction layer mangling `patch`/`write_file` content — distinct cause (brand-scrub transport vs redaction layer), identical fix: dynamically-constructed literals via `execute_code` + on-disk byte verification.

### Assuming captures are pristine

If the proxy captures both pre-transform and post-transform bytes, the file naming matters: `-in-raw.json` (pre-forward-transform inbound), `-out.json` (pre-forward-transform outbound from proxy's perspective), `-in.sse` (post-reverse-transform server-sent events going back to harness). Pick the right capture for the question you're asking. Mixing them up will make a working transform look broken or vice versa.

## Bug class: straddling needles in retain-tail buffers

A common middleware pattern is: buffer streamed text, keep the last `N-1` chars as a "retain tail" to catch a needle that straddles a delta boundary, flush the rest as "safe."

The naive implementation has a subtle leak: when a needle occurrence sits at position `p` such that `p < splitAt < p + needleLen`, the needle's **head** is in the safe slice and its **tail** is in the retained suffix. The reverse-map sees only the head, doesn't match, and emits the head unreversed. The next feed combines `suffix + new_chunk` and the suffix starts AFTER the needle's start, so the head is permanently lost.

### Recognition signature

- Streaming output mostly works, but ~1 in N occurrences of a substitution target leaks through unreversed.
- The leak position is reproducible: it always lands at the same byte offset relative to some upstream chunk boundary.
- Adding the needle to a buffer's "protected" list eliminates the leak.

### The fix pattern

```js
function feed(buf, chunk, needles, retain) {
  const combined = buf + chunk;
  if (combined.length <= retain) return { safe: '', suffix: combined };
  let splitAt = combined.length - retain;
  // Back off splitAt past any needle that straddles the boundary
  for (const needle of needles) {
    const L = needle.length;
    const searchFrom = Math.max(0, splitAt - L + 1);
    if (searchFrom >= splitAt) continue;
    let idx = combined.indexOf(needle, searchFrom);
    while (idx !== -1 && idx < splitAt) {
      if (idx + L > splitAt) splitAt = idx; // keep needle whole in suffix
      idx = combined.indexOf(needle, idx + 1);
    }
    if (splitAt <= 0) break;
  }
  const safe = combined.slice(0, splitAt);
  const suffix = combined.slice(splitAt);
  return { safe, suffix };
}
```

Cost: O(needles × combined.length) per feed, which sounds bad but in practice `combined.length` is bounded by chunk size + retain (small) and the search window per needle is bounded by `needleLen` chars.

### Test fixtures

Minimum coverage to catch straddler bugs:
- **Every possible split position of the longest needle.** Iterate `i` from 1 to `needleLen-1`, splitting the needle at index `i` across two deltas. All should round-trip.
- **A pre-fix simulation.** Construct the buffer with an EMPTY needle list and assert the leak occurs. This documents the bug class and prevents future refactors from silently re-introducing it.
- **Three-way splits.** A single needle split across three or more deltas. Boundary conditions tend to compound.
- **Multiple needles in one delta** where only one straddles.

See `~/claude-api-proxy/test/parity/v2.9.2-straddling-needle.test.js` (11 tests) for a worked example.

## Bug class: stateless code-span regex on streaming slices

Another transform-layer leak appears when code-span protection is correct for whole strings but is applied to arbitrary streamed slices. A regex such as ``/```[\s\S]*?```|`[^`]+`/g`` cannot know whether a boundary backtick is opening or closing when the slice begins/ends inside an inline code span.

### Recognition signature

- Reverse mapping works for whole prose and for whole SSE events, but a streamed chat chunk leaks a sentinel or sanitized token in normal prose.
- The leaked token appears between two inline-code spans, e.g. `` `some-code` so SENTINEL's `next-code` ``.
- Running the same string without backticks reverses correctly.
- Existing “sentinel inside code span is protected” tests pass, because this is not a real code-span case; it is prose misclassified as code by a stateless slice-local regex.

### The fix pattern

Track code-span state across streamed text deltas, then apply substitution only to ordered prose segments:

1. Maintain per-content-block state: outside / inline-code / fenced-code.
2. Segment each emitted safe slice into ordered `{kind: 'safe'|'code', text}` pieces using that state.
3. Apply reverse mapping to `safe` pieces with code-span protection disabled, because streaming context already classified them.
4. Emit `code` pieces unchanged.
5. Preserve any existing retain-tail buffer for split substitution needles; the code-span state and needle-retain buffer solve different boundary bugs.

Do not “fix” this by weakening the global code-span regex; whole-string non-streaming paths still need that protection. Do not buffer the whole assistant block unless you intentionally accept a streaming-latency regression.

### Test fixtures

- A valid concatenated stream where chunk 1 emits an opening backtick and chunk 2 starts with the retained code-prefix + closing backtick + sentinel prose + opening backtick for the next code span. Current buggy code leaks; stateful segmentation passes.
- Sentinel inside an actual inline-code span remains unchanged.
- Fenced code split across deltas remains protected.
- Ordered mixed output (`safe → code → safe → code → safe`) preserves order.

## Worked example: claude-api-proxy v2.9.2 (2026-05-13)

Session story:
1. Designed gauntlet to stress-test newly-shipped v2.9.1.
2. Emitted dense paragraph hitting every forward-substituted token.
3. Tried to count substitution targets in the SSE capture file — but my counting Python script's own string literals got forward-substituted by the proxy in flight.
4. Switched to base64 / charcode-based inspection. Found 1 leak out of 34 substitution-target occurrences.
5. Diagnosed via the SSE capture: leak was at the *first* occurrence of `\`<target>\`` in the dense paragraph, which straddled a delta boundary from Anthropic.
6. Root cause: `makeSseDeltaBuffer.feed` computed `splitAt` without checking for straddling needles.
7. Fix: add `collectReverseNeedles(config)` helper, pass needles to buffer, back off `splitAt` past any straddler.
8. Test: 11 cases including every-split-position, longest-needle, three-way-split, PascalCase variant, pre-fix simulation that documents the bug.

Total time from leak detection to merged PR: ~25 minutes. Without the dynamic-string-construction technique the tests would have been impossible to author through the same proxy.

## Related skills

- `software-development/systematic-debugging` — parent skill, this is a reference under it
- `software-development/integration-archaeology` — for reverse-engineering the transform layer before debugging
- `software-development/test-driven-development` — the test-fixture-diversity discipline (the casing-collision pitfall) applies doubly here

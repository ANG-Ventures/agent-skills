# Proxy/Bridge Live Provider Quirks

Use this reference when debugging a local proxy/bridge that emulates a real SDK/CLI against a live provider. Keep offline mocks first, then run the cheapest live probes needed to validate wire-shape.

## Streaming shape vs OpenAI-compatible default

- OpenAI-style APIs should default to non-streaming unless the request asks for streaming.
- Some provider-specific emulation paths may require streaming-shaped requests for fidelity. For Claude Code OAuth emulation, live requests with `stream: true` should send `Accept: text/event-stream`; mismatching `stream: true` with JSON accept headers can produce provider/CDN 400s before the application layer gives a useful error.
- Do not paper over this by making every request streaming. Preserve the caller's stream choice, then make the live test/helper headers match that choice.

## Hop-by-hop headers

When a proxy reads and rewrites a request body, strip hop-by-hop headers before forwarding upstream. In particular, never forward `transfer-encoding: chunked` alongside a newly synthesized `content-length`; CDNs/providers may reject the request with opaque 400s.

Strip at least:

- `connection`
- `transfer-encoding`
- `te`
- `trailer`
- `upgrade`
- `keep-alive`
- `proxy-authenticate`
- `proxy-authorization`
- `proxy-connection`
- `expect`

Add regression tests that inspect the fake upstream's received headers so this does not silently regress.

## Anthropic Messages cache_control placement

For Anthropic Messages API, `cache_control` belongs on cacheable content/tool blocks, not as a top-level request property. A top-level `cache_control` may be ignored or rejected depending on path/provider behavior.

Durable pattern:

1. Remove any invalid top-level `cache_control` when injection is enabled.
2. Attach `{ type: 'ephemeral', ttl: '5m' | '1h' }` to a text content block:
   - prefer the last system text block;
   - otherwise use the last user text content block;
   - preserve tool/thinking blocks byte-for-byte unless explicitly opting into a separate cleanup.
3. Count injection metrics separately from body transformation purity.

## Live cache verification

Cache tests need to cross the model's real cacheable-prefix floor and must be deterministic across request 1 and request 2.

- First request should show `cache_creation_input_tokens > 0` unless already warm.
- Second identical request should show `cache_read_input_tokens > 0`.
- If both are zero but the request succeeds, suspect either cache_control placement or prefix length before blaming provider state.
- Use cheap models by default and make live/expensive probes opt-in via env flags.

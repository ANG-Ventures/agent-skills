# Pipeline-Aware Testing

When you add a new transform (helper, middleware, layer) to a code path that
already has prior transforms running before yours, naive unit tests trip on
two predictable failures. Encode the discipline upfront so you don't waste
iterations on test-side noise.

## Failure mode 1 — Unit assertions that assume the raw input shape

You write `wrapMcpToolName('sessions_list') === 'mcp__assistant__List_tasks'` as
a unit test for a pure helper. The function is pure and does exactly what it
says. But your *integration* assertion uses the same expected value, even
though the integration path runs Layer 2 string replacements *before* your
helper and rewrites `sessions_list → ` to something else first. The helper sees
post-Layer-2 input, produces a different (correct) output, and your assertion
fails.

**Rule:** Pure-function unit tests assert on what the function does in
isolation. Integration tests must compute expected values against the
*pipeline's input transformation*, not the raw fixture you typed.

Concretely, when you author the integration test:
1. Identify every transform that runs before your new helper.
2. Either pick a fixture value that's a fixed-point under all prior
   transforms (recommended), or write the expected output by mentally
   running each prior transform.
3. Better still, assert on a *property* that survives all upstream
   transforms — `parsed.tools.some(t => t.name.startsWith('mcp__assistant__'))`
   instead of `parsed.tools[0].name === '<exact>'`.

## Failure mode 2 — Existing tests asserting on pipeline output

When you add a transform to the pipeline (e.g. appending `?beta=true` to the
upstream URL), every existing test that asserted on the *old* pipeline output
will break. The break is correct — the pipeline genuinely changed. But it
looks like your change broke unrelated tests, which costs review cycles.

**Rule:** Before running `npm test` / `pytest`, grep the test tree for any
assertion that mentions the value(s) you're about to change.

```bash
# Examples
grep -rn "'/v1/messages'" test/        # before adding ?beta=true
grep -rn "upstreamSeen.options.path"   # before changing forwarded path
grep -rn "system\.length === 2"        # before relocating system entries
```

Update every match in the same patch. They're not flaky — they're load-bearing
assertions that document the pipeline contract. The patch should change them
deliberately and call them out in the commit message.

## Failure mode 3 — Metric counts that are brittle

If your transform produces a metric (`metrics.parity.mcpToolsWrapped`), the
integration count includes side-effect tools the pipeline injected
(e.g. CC_TOOL_STUBS). Asserting `=== 1` for "I added one tool to the fixture"
ignores the injected ones. Either:

- Assert `>=` against the lower bound you control, or
- Filter the metric source to the fixture-controlled subset before counting.

## Authoring checklist for additive pipeline transforms

Before writing the test file:

- [ ] List every transform that runs before yours in the pipeline.
- [ ] Pick fixture values that are fixed-points under those prior transforms
      (e.g. PascalCase names like `Calculator` that survive lowercase string
      replacement passes).
- [ ] Grep existing tests for assertions on the same pipeline output values
      your change will affect.
- [ ] Write property-shaped assertions (`startsWith`, `includes`,
      `some(...)`) over exact-value assertions when the prior pipeline can
      mutate the value.
- [ ] For metric assertions on integration tests, use `>=` not `===` unless
      you're certain nothing else in the pipeline produces the same metric.

## Real-world example (claude-api-proxy v2.4.0)

Adding `wrapToolNamesMcp` after Layer 2 string replacements meant:

- Fixture `tools: [{ name: 'calculator' }]` → Layer 2 leaves it →
  wrap produces `mcp__assistant__Calculator` ✓
- Fixture `tools: [{ name: 'sessions_list' }]` → Layer 2 rewrites `sessions_list` →
  wrap produces `mcp__assistant__Sessions_list` (NOT `mcp__assistant__List_tasks`)
- Fixture `system.length === 2` → relocation moves text entries → integration
  metric is `2` not `1` because the pipeline parsed two separate text entries
  not the one I'd modeled in my head.

Path-assertion tests in `test/proxy.test.js` and
`test/e2e/robustness.test.js` both broke when `?beta=true` was added. They
were the same logical fix (update assertion to new pipeline output) but I
only caught one in the first pass.

## Cross-reference

When testing a transform inside a multi-layer pipeline, also load:
- `software-development/systematic-debugging` — if assertions fail
  unexpectedly, root-cause why before relaxing the assertion. A "brittle
  test" is sometimes a real bug in the new transform.

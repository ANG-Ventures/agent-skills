# Instrument before guessing when the LLM's behavior is the symptom

Companion to Phase 1 step 4 ("Gather Evidence in Multi-Component Systems"). This reference captures a specific class of bug where source-code reasoning misleads worst, and the recommended instrumentation pattern.

## When this pattern applies

You are debugging a system where:
- An LLM is somewhere in the loop (proxy, harness, agent, prompt pipeline)
- The symptom is "the model did something unexpected" — invalid tool call, refused, hallucinated, wrong format, broke after a config change
- You have a hypothesis based on reading code

This is the case where source-code reasoning misleads you most, because **the model is not reading your source code — it is responding to whatever request bytes actually reach Anthropic/OpenAI/etc.** Your hypothesis about which transform fired is hypothesis-only until you see the bytes.

## The trap (real example, 2026-05-12)

A proxy started causing invalid tool calls after enabling a new "MCP tool-name namespacing" feature. Two days were spent across v2.4.0 → v2.4.1 → v2.5.0 building architectural fixes for the namespace leak (in-process plugin patches, loud-fail self-tests, full architecture docs about wire-vs-harness boundaries).

Adding 50 lines of body-capture instrumentation answered the question in one live request:

- The MCP namespace wrap never fired (flag plumbing had a silent bug we missed).
- The real cause was a pre-existing, unrelated feature (`injectCCStubs`) that hardcoded 5 fake Claude Code tool schemas into every outgoing request. As other disguise improvements landed (Stainless headers, billing fingerprint, identity match), the model became confident enough to *call those fake tools*. The harness then rejected the call because the tool didn't exist on the harness side.
- Two days of architectural work was diagnosing the wrong feature.

The cost of guessing without instrumentation: ~2 days, 3 shipped "fix" versions, 2 elaborate architecture docs. The cost of instrumentation: 50 lines, 20 minutes, one definitive answer. The actual fix once the real bug was known: 20 lines (a de-dup helper) + one opt-out config flag.

## Compounding dividends (v2.7.0 follow-up, same session)

Once the instrumentation existed, it kept paying out. Using the *same* `captureBodies` feature for the very next investigation (whether MCP namespacing was salvageable at all) immediately surfaced two follow-on findings the source-code reasoning had also missed:

1. The "MCP flag plumbing is broken" diagnosis from v2.4.1 was wrong. The flag *does* fire — earlier captures had been taken under conditions that masked it. Instrumentation revealed it was working as specified.
2. Anthropic's response behavior is non-deterministic with respect to the MCP namespace: with hardcoded tool stubs present, Anthropic strips the namespace before echoing; with stubs absent, Anthropic preserves the wrapped name verbatim. No amount of code reading would surface this — it is purely a property of the upstream model API, observable only at the byte level.

Lesson: **the instrumentation outlasts the bug it was built for.** If you build it for one diagnostic, keep it (gate it behind a config flag) and reach for it the next time you have a behavioral question. Building a second copy from scratch for the next investigation is a clean-architecture smell, not a code-hygiene win.

## The elaborate-fix temptation (why this trap is sticky)

Each of the wrong fixes (v2.4.0, v2.4.1, v2.5.0) *felt like progress*. Each one passed its own offline tests, shipped cleanly, even came with architecture documentation about why this was the correct layered solution. The seductive part is that source-code reasoning produces *coherent stories*: "the wire layer can't see into the harness's tool dispatcher, therefore we need a plugin, therefore we need a loud-fail self-test for when the plugin breaks…" Every step in that chain is technically defensible.

The chain is still wrong if the original hypothesis was wrong.

**Treat any of these as a stop-and-instrument signal, not a green light to keep going:**

- You are about to ship a third revision of a fix for the same underlying symptom.
- The fix requires new architectural concepts (a new plugin, a new layer, a new compatibility shim) to explain itself.
- Your test suite passes locally but the symptom returns the moment real model traffic hits the system.
- The fix's value depends on a behavioral claim about the model ("the model will/won't do X") that you have not observed in actual traffic.

## The general principle

**Build a way to observe the model's actual inputs and outputs before building a fix.** Especially when the symptom is "the model behaved unexpectedly." That is exactly the case where source-code reasoning misleads worst.

Corollary: when reasoning about why an LLM did X based on what your code does, that is a **hypothesis**, not a finding. It needs evidence to graduate.

Second corollary: **the instrumentation is an investment, not a one-shot tool.** Build it cheap, gate it behind a flag, leave it in. Future diagnostics reuse it. (See "Compounding dividends" above.)

## Minimum useful instrumentation for an LLM-in-the-loop system

When the system is an HTTP proxy/sidecar between harness and model API:

1. **Capture the body the harness sent in** (pre-transform).
2. **Capture the body you sent to the model API** (post-transform).
3. **Capture the body the model API returned** (pre-reverse-transform).
4. **Capture the body you sent back to the harness** (post-reverse-transform).

All four matter. (3) was the one we initially skipped, and it was the one that revealed Anthropic's non-deterministic namespace handling. Don't trust that you know what the upstream API will do — capture and look.

Cheap implementation (Node.js example, ~50 lines):

```js
const captureBodies = config.captureBodies === true;
const captureDir = config.captureDir || '/tmp/proxy-capture';

function maybeCapture(label, body, reqNum) {
  if (!captureBodies) return;
  try {
    if (!fs.existsSync(captureDir)) fs.mkdirSync(captureDir, { recursive: true });
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const path = `${captureDir}/${ts}-${String(reqNum).padStart(4, '0')}-${label}.json`;
    // optionally elide noisy fields (long billing blocks, etc.) before writing
    fs.writeFileSync(path, body.slice(0, 200_000));
  } catch (e) {
    // never let capture failures break the request path
  }
}
```

Wire into the request handler at the four points above. Gate behind a config flag (default off) so prod cost is zero.

If the system is in-process (no HTTP boundary), the equivalent is logging at function entry/exit on the transform pipeline, with a structured logger that can be enabled per-session.

## Test-fixture diversity for transform functions

A separate but adjacent anti-pattern surfaced in the same session: the casing-collision bug (`unwrap('mcp__assistant__Glob')` → `'glob'` when Hermes registered `Glob`) was **caught only by instrumentation against production-shaped names**. The unit test suite had only ever passed `'calculator'` and `'bash'` (lowercase) as wrap inputs, so the lowercase-first unwrap rule looked correct.

The lesson generalizes: **for a transform that is supposed to be casing/encoding/format-preserving, the test fixtures must exercise the full diversity of inputs production will see.** If your tests only use one casing, your transform is only verified for that casing.

When writing tests for wrap/unwrap, encode/decode, escape/unescape style functions, include at minimum:

- Lowercase-first inputs
- Uppercase-first inputs
- Snake_case inputs
- Mixed-case inputs
- Empty / single-character inputs
- Already-transformed inputs (idempotency check)
- And a single `wrap+unwrap === identity` round-trip test across all of them

This is cheap to write and would have caught the bug at PR time instead of at production-deploy time.

## How to interpret captures when the bug is "model behaved wrong"

Diff the bytes the model **actually saw** against the bytes you **think** you sent:

- Did the transform you suspect actually fire? Grep for its fingerprint in the post-transform body.
- Did the model receive any text the user/harness did not intend? (System prompts merged wrong, leftover debug headers, etc.)
- Are there fields in the tools array, system prompt, or messages the model is "discovering" that suggest behaviors not in the user's request? (e.g. injected stubs, hardcoded tool descriptions, identity-priming text.)
- Did the response include names/values that don't exist on the harness side?
- Did the upstream API mutate the request shape in unexpected ways? (See the Anthropic namespace-strip example above.)

The bytes are ground truth. The code is a description of bytes that may or may not be running.

## How to wire this into the four-phase debugging flow

Phase 1 ("Gather Evidence") for LLM systems gains one mandatory sub-step:

> **Before forming a root-cause hypothesis about the model's behavior, capture the exact request bytes the model received and the exact response bytes it returned.** Source-code reasoning is a hypothesis-generator at best.

If you find yourself building architecture-level fixes ("we need to restructure the plugin", "we need to add a new layer") on the basis of *which transform should have run*, stop. Add instrumentation, confirm what actually ran, then decide what to fix.

## Anti-patterns that this prevents

- Building elaborate fixes for the wrong feature because the failure mode "looked like X" based on code reading.
- Disabling features defensively (deprecating a flag, ripping out code) when the flag was never actually firing.
- "Fixing" the same bug across multiple versions because each version's fix targeted a symptom of a different real bug.
- Spending compute on subagent rounds that all reason from the same flawed source-code hypothesis.
- Writing transform tests with homogeneous fixtures, so the test suite is green but production fails on a casing/encoding/shape the tests didn't cover.
- Rebuilding diagnostic instrumentation from scratch for each new investigation instead of leaving the previous one in (gated) for reuse.

## When NOT to bother

- Bug is in a pure deterministic transform (no LLM): source-code reasoning is fine. Add tests, not captures.
- The instrumentation cost exceeds the bug's blast radius (e.g. one-off cosmetic issue).
- You already have logs that answer the question. Read them first.

## See also

- Parent: `software-development/systematic-debugging/SKILL.md` Phase 1 step 4.
- Companion: `references/proxy-bridge-live-provider-quirks.md` (wire-shape pitfalls for proxy/bridge work specifically).

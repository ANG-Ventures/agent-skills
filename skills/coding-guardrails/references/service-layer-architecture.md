# Service-Layer Architecture — where shared logic belongs

> **Provenance:** vendored 2026-06-15, adapted from `michaelshimeles/skills` →
> `code-structure/SKILL.md` (MIT-spirit, idea-mined not copied wholesale). Folded into
> `coding-guardrails` as a reference rather than a standalone skill: it's the *placement*
> companion to the guardrails' *change-discipline* — load it when refactoring repeated
> operational logic or deciding what belongs in an action vs a shared service.
>
> **Boundary vs the guardrails body:** the main skill answers "how do I make THIS change
> minimally and prove it." This reference answers "WHERE should the logic live, and when do
> I extract it." It extends — does not override — the "generalize on the second real use, not
> the first imagined one" rule.

## When to reach for this

- Multiple callers need the same low-level operation (sandbox creation, email send, payment,
  a provider/SDK call, a retry+health-check dance).
- You're copy-pasting an operational block between action/handler files.
- A bug fixed in one workflow doesn't propagate to the others doing the same thing.
- You're adding a feature that shares mechanics with an existing flow.

**Do NOT reach for it when** the logic is genuinely domain-specific and has exactly one
caller. Extracting a single-use block is over-abstraction — the precise failure the
guardrails' "minimum code, no speculative abstraction" rule warns against. The extraction
trigger is **logic repeated across 2+ real callers**, never an imagined second use.

## The two-layer split

```
Orchestration Layer (Actions / handlers)   Service Layer (shared mechanics)
├── owns business rules (why/when)          ├── owns reusable operations (how)
├── owns state transitions                  ├── owns provider/SDK interactions
├── owns auth / ownership checks            ├── owns command-execution details
├── owns failure CLASSIFICATION             ├── owns health checks / readiness
├── owns retries / user-facing errors       └── returns STRUCTURED results
└── calls service functions
```

Rule of thumb:
- *"What this product flow MEANS"* → keep in the **action** (auth, policy, status
  transitions, error classification, user-facing messaging).
- *"How to do this operation reliably"* → move to the **service layer**.

The action decides *whether/when* to send the welcome email (marketing opt-in vs admin
invite — two different business rules); the service owns *how* to send it (the one
`sendWelcomeEmail(...)` mechanic both reuse). Two business rules, one mechanic.

## Designing service functions — capability blocks, not god-methods

Design as small composable capabilities, so each caller picks what it needs and chooses
strict-vs-relaxed behavior per flow:

```
createManagedSandbox(...)
prepareRepo(...)
detectPackageManager(...)
installDependencies(...)
runBuildCommand(...)
startSandboxRuntime(...)
```

Each service function must:
- Accept all required data as **explicit parameters** (no reaching into globals/request).
- Return **structured outputs** (`{ ready, previewUrl, proxyPort }`), not bare booleans.
- **Never** reach into the database / mutate domain state directly — that's the action's job.
- Make failure **explicit** (structured result or typed throw) — never a swallowed error.

## Extraction / migration checklist (one caller at a time)

This is the "smallest viable diff" rule applied to a refactor — migrate incrementally, prove
each step, never big-bang:

1. Write the flow in the action first, with clear behavior.
2. Mark the repeated operational chunks across callers.
3. Extract **only** the repeated, non-domain chunk to the service.
4. Replace **one** caller → verify it still works → then migrate the rest.
5. Keep domain policy in the action (auth, status transitions, error classification).
6. Run verification: typecheck, lint, and confirm every migrated flow still works on its
   real path (per the guardrails' "prove it on the original path" rule).

## Anti-patterns

| Anti-pattern | Problem |
|---|---|
| **God service** | One huge function hides all control flow; nobody can reuse a piece. |
| **Leaky service** | Service mutates DB tables / domain state directly — blurs the layer. |
| **Inconsistent API** | Each function uses different arg styles / error semantics. |
| **Over-abstraction** | Extracting logic used by only ONE caller (premature DRY). |

## One-sentence model

*Actions orchestrate domain rules; the service layer centralizes reusable operational
mechanics behind a composable, explicit-input, structured-output API — and you only extract
once the same mechanic has two real callers.*

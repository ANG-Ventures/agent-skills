# PRD template with verification blocks

Use this as a starter skeleton for PRDs/specs that will be reviewed and built.

```markdown
# PRD — [System / Feature]

**Version:** v1 (pre-review)
**Date:** YYYY-MM-DD
**Author:** the orchestrator agent
**Owner:** the orchestrator agent
**Status:** DRAFT

## 1. Summary & Goal

[What changes, why now, and what success looks like.]

## 2. Non-Goals

- [What explicitly does not ship.]

## 3. Resolved Decisions

| # | Decision | Value / rationale |
|---|---|---|
| D1 | [decision] | [why] |

## 4. Architecture / Design

[Diagram or prose. Include data flow, control flow, storage, external services.]

## 5. Implementation Phases

- **Phase 0 — Hard gate / spike.** [Prove the load-bearing premise.]
  - *Unit/script check:* [narrow check]
  - *E2E/integration check:* [real input on real path] OR `Not applicable: [reason]`
  - *Negative/adversarial:* [bad/trust case] OR `Not applicable: [reason]`
  - *Evals (if ML/heuristic/model):* [metric + target]
  - *Verify with:* `[command]` → [expected result]

- **Phase 1 — [name].** [What ships.]
  - *Unit/script check:* [...]
  - *E2E/integration check:* [...]
  - *Negative/adversarial:* [...]
  - *Evals (if ML/heuristic/model):* [...]
  - *Verify with:* `[command]` → [expected result]

## 6. Security / Privacy / Ops

- Credentials/secrets: [storage, redaction, no logs]
- External actions/public surfaces: [gates]
- Failure alerts: [where, format]
- Rollback: [exact rollback]

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| [risk] | [impact] | [mitigation] |

## 8. Open Questions

1. [Only real unresolved question]

## 9. Acceptance Criteria

- [ ] [Criterion] — Evidence: [test/eval/doc/git output]
```

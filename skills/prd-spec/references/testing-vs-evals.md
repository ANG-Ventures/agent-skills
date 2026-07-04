# Testing vs evals in PRDs

Use this reference when deciding what belongs in a phase Verification block.

## Tests

Tests are pass/fail correctness checks. Use them for deterministic requirements:

- parser returns the right fields;
- API endpoint returns a stable schema;
- service starts and health check passes;
- bad input returns a structured error;
- persisted data round-trips.

Good tests name the command, the input, and the expected output. For any new/changed real path, include at least one no-mock end-to-end test.

## Evals

Evals measure quality or behavior that is not simply pass/fail:

- transcription word error rate / rough transcript quality;
- retrieval recall@k or semantic-search hit rate;
- ranking preference fit;
- summarization factuality / coverage;
- latency, throughput, cost, GPU memory;
- model fallback quality deltas.

A good eval includes:

1. metric name;
2. representative sample/corpus;
3. target threshold;
4. baseline/comparison if possible;
5. failure action if the target is missed.

## Boundary rule

If a phase changes one of these, require e2e:

- network/service calls;
- filesystem/persistence/schema;
- external process spawning;
- GPU/model inference;
- auth/secrets/trust boundaries;
- user-facing commands/UI;
- cron/scheduler/alerts.

If none apply, write `Not applicable: [one-line reason]` rather than inventing fake e2e.

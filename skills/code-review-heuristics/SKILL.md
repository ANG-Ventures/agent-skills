---
name: code-review-heuristics
description: "Local addendum of high-yield review heuristics that catch real bugs (guard parity across parallel code paths, unit-test masking of integration gaps, dead-code sweeps after vN+1 rewrites). Load alongside github-code-review when reviewing PRs or doing a repo scan."
platforms: [linux, macos, windows]
metadata: {"hermes":{"tags":["Code-Review","Quality","Heuristics","Pull-Requests"],"related_skills":["github-code-review","verifying-beyond-green-tests"]}}
---

# Code-review heuristics (local addendum)

Extends the (read-only, hub-installed) `github-code-review` skill with heuristics that have caught
CRITICAL findings on this fleet. Apply these on every PR batch review or whole-repo scan.

## 1. Parallel-path guard parity (top-yield check)

When a PR adds a guard / filter / suppression / sanitizer to one code path, enumerate every SIBLING
path that handles the same inputs and verify the guard applies there too:

- feature-flagged variants (env-switched: legacy vs new route)
- sync-on vs sync-off lanes, prod vs CI configs
- carve-outs / fast-paths that run BEFORE the guarded lane in precedence order

Ask explicitly: **"which lane actually runs in production, and is THAT lane guarded?"** The classic
miss (found live, ha-command-router PR #7, 2026-07-01): a deliberative-utterance suppression was added
only to the curated lane, while the feature-flagged superset path — the one live in prod — had
earlier-precedence lanes with no check. The tests only exercised the hermetic default config, so they
were green while the deployed path leaked.

Corollary: **tests that only run under the default/hermetic config prove nothing about the flagged
path.** If a test file comments away the flagged variant ("excluded from this hermetic no-sync test"),
that's a finding, not a footnote — demand a test with a fake/injected adjunct for the flagged lane.

## 2. Integration-vs-unit masking

If new code READS a field from another component's output (e.g. a scorer reading
`plan["matched_alias"]`), grep the PRODUCER to confirm that field is ever actually emitted at runtime.
Tests that hand-construct the input dict with the field present mask the integration gap completely.
One `grep -rn '"matched_alias"' <producer>/` settles it in seconds.

## 3. Dead-code sweep after a v2 replaces a v1

When a PR ships "v2" of a function/module, grep for remaining callers of the v1 API (runtime AND
tests AND tools). Common leftovers: the v1 entrypoints with zero callers, a measurement harness still
computing v1-only inputs it never uses, a module docstring still describing v1. Two coexisting scorers
/ parsers with the same module name invite the wrong one being wired later — flag deletion or a move
to `tools/`.

## 4. Load-time vs per-call misplacement (optimization scans)

In hot matching/dispatch loops, look for normalization or preprocessing of STATIC data (registry
aliases, config phrases) being recomputed per request per item. If a PR grows the static set (e.g. a
grammar expander multiplying alias counts), the per-call cost scales silently. The fix is always the
same shape: precompute `(normalized, stripped, len)` tuples at load, compute the per-request side once
per call. Also watch for the same expensive probe being called twice in one request (an overlap check
followed by the real call with identical args) — cache the first result.

## 5. Reporting

Use the Critical / Warnings / Suggestions / Looks Good format from `github-code-review`, with
`file:line` anchors and a one-line concrete fix per finding. For multi-PR batch reviews, keep findings
grouped by severity across PRs (not per-PR) and end with a "process notes" paragraph stating exactly
what was read vs executed, and that nothing was mutated.

## Tooling note

On rtk-enabled hosts, `grep` with alternation/parens may be rewritten to `rtk grep` (Rust-regex
dialect: BRE `\|` escapes and bare `(` fail with "unclosed group"; piped chains can return rtk's usage
text as fake data). Use `/usr/bin/grep` by absolute path or `search_files` — see
`rtk-terminal-compression` pitfalls.
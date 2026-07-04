---
name: mast-failure-modes
description: >
  Canonical reference — the MAST (Multi-Agent System Failure Taxonomy): 14 empirically-ranked
  failure modes for multi-agent LLM systems, from UC Berkeley's "Why Do Multi-Agent LLM Systems
  Fail?" (arXiv:2503.13657v3, 1,642 annotated traces, κ=0.88). Load this as a design/lint checklist
  whenever you are DESIGNING, REVIEWING, or DEBUGGING a multi-agent / fan-out / subagent system —
  deep-research fan-out, delegate_task / subagent-driven-development briefs, Kanban swarm plans.
  Not a procedure; a "documented ways agent systems fail" rubric that other skills point at.
metadata: {"source": "arXiv:2503.13657v3 (Cemri et al., UC Berkeley, rev 2025-10-26)", "license": "paper CC BY-NC-ND 4.0"}
---

# MAST — Multi-Agent System Failure Taxonomy (shared reference)

A checklist of **the documented ways multi-agent LLM systems fail**, ranked by how often they actually
occur. From UC Berkeley's *Why Do Multi-Agent LLM Systems Fail?* — 14 failure modes derived from 1,642
annotated execution traces across 7 MAS frameworks, validated at inter-annotator κ=0.88. Open-source MAS
showed a **41%–86.7% failure rate**; this taxonomy is the empirical map of *why*.

> **Use this as a lint rubric, not prose.** When designing/reviewing/debugging any fan-out, subagent, or
> swarm workflow, walk the 14 modes and ask "is my design exposed to this one?" The percentage tells you
> where to spend guardrail budget — the top modes (FM-1.3 15.7%, FM-2.6 13.2%, FM-1.5 12.4%, FM-1.1
> 11.8%) account for the bulk of real-world failures.

## The 14 modes (exact prevalence from the paper)

### FC1 — System Design & Architecture (pre-execution flaws that surface at runtime)
| Mode | Name | % | What it looks like |
|---|---|---|---|
| **FM-1.1** | Disobey task specification | **11.8%** | Ignores stated requirements/constraints (e.g. uses a fixed word bank when told not to). Often a design/prompt flaw, not just LLM weakness. |
| FM-1.2 | Disobey role specification | 1.5% | An agent acts outside its assigned role (e.g. a sub-role ends the conversation without the lead's consensus). |
| **FM-1.3** | Step repetition | **15.7%** | **#1 mode.** Redundantly repeats already-completed steps; loops without progress. |
| FM-1.4 | Loss of conversation history / context | 2.8% | Drops earlier context, regresses to an earlier state. |
| **FM-1.5** | Unaware of termination conditions | **12.4%** | Doesn't recognize the task is done (or can't be done); keeps going past sufficiency. |

### FC2 — Inter-Agent Misalignment (coordination breakdowns)
| Mode | Name | % | What it looks like |
|---|---|---|---|
| FM-2.1 | Conversation reset | 2.2% | Unexpected restart, losing accumulated progress. |
| FM-2.2 | Fail to ask for clarification | 6.8% | Proceeds on a wrong assumption instead of asking when the brief is ambiguous. |
| FM-2.3 | Task derailment | 7.4% | Drifts off the assigned objective. |
| FM-2.4 | Information withholding | 0.85% | An agent has crucial info but doesn't share it with peers who need it. |
| FM-2.5 | Ignored other agent's input | 1.9% | Receives a peer's contribution and disregards it. |
| **FM-2.6** | Reasoning–action mismatch | **13.2%** | #2 mode. What the agent *does* doesn't match what it *reasoned* (says X, does Y). |

### FC3 — Task Verification & Termination (output quality control)
| Mode | Name | % | What it looks like |
|---|---|---|---|
| FM-3.1 | Premature termination | 6.2% | Ends before the objective is actually met. |
| FM-3.2 | No or incomplete verification | 8.2% | Output isn't checked (or only superficially) — passes a shallow check while wrong. |
| FM-3.3 | Incorrect verification | 9.1% | A verification step runs but validates the wrong thing / accepts a bad output. |

*(FC3 combined ≈ 23.5% — nearly a quarter of all failures are verification/termination quality.)*

## The 3 design insights (the paper's prescriptive takeaways)
1. **Failures are mostly design, not model.** Many modes (esp. FC1) trace to MAS architecture, role
   definitions, and prompt specs — fixable without a better LLM. A single role-spec fix gave **+9.4%**
   task success on ChatDev with the same prompt + model.
2. **A verifier is not a silver bullet.** Systems with explicit verifiers (MetaGPT, ChatDev) fail less,
   but presence of a check ≠ correctness — superficial checks pass broken output (FM-3.2/3.3).
3. **Multi-level verification is needed.** Sole reliance on final-stage, low-level checks is inadequate;
   adding a high-level *objective* verification step gave **+15.6%** on a program-dev benchmark. Verify
   against the brief's intent, not just per-claim/per-line.

## How fleet consumers apply MAST (the routing)
| Consumer | MAST modes it most needs to guard | Mechanism already in place |
|---|---|---|
| `deep-research` (fan-out loop) | FM-1.3 (step repetition), FM-1.5 (termination), FM-2.4 (withholding across workers), FC3 (verification) | §3 router, §5 cluster-merge, §7 separate citation/verification pass |
| `delegate_task` / `subagent-driven-development` (worker briefs) | FM-1.1 (disobey spec, **most prevalent single mode**), FM-2.2 (no clarification), FM-2.3 (derailment) | Standalone brief: objective + boundaries + format + tool-guidance + **effort budget** |
| `prd-swarm-plan-review` (swarm-plan lint) | all 14 — it's a pre-dispatch design review | Use this table as the lint rubric |

## Anti-patterns this taxonomy explains (concrete)
- **"3 subagents redundantly investigating the same sub-question"** → FM-1.1 + FM-1.3 (under-specified
  delegation → step repetition). Fix: explicit scope boundaries + per-worker effort budget.
- **"Perfectly cited report that doesn't answer the question"** → FM-3.2/3.3 (verification checked the
  wrong axis). Fix: task-level verification gate distinct from citation-checking.
- **"Agent kept searching after it had enough"** → FM-1.5. Fix: sufficiency-first stop ("do I already
  have enough to answer the brief?"), name the termination condition explicitly.

## Source
- Cemri, Pan, Yang, Agrawal, Chopra, Tiwari, Keutzer, Parameswaran, Klein, Ramchandran, Zaharia,
  Gonzalez, Stoica. **"Why Do Multi-Agent LLM Systems Fail?"** arXiv:2503.13657v3 (UC Berkeley + Intesa
  Sanpaolo, submitted 2025-03-17, rev 2025-10-26). <https://arxiv.org/abs/2503.13657>
- Percentages are the v3 Section-4 prevalence figures over 1,642 traces. Dataset/taxonomy/annotator
  released publicly (`pip install agentdash`, per the paper). License CC BY-NC-ND 4.0.
- Surfaced for the fleet by the research agent during the 2e SOUL self-critique (agentic-absorption project),
  2026-06-10.

# SOUL.md Archetypes

Role-pure, agent-agnostic identity documents ("souls") for Hermes agents — the file that defines
*who an agent is*: its role, values, autonomy boundaries, verification discipline, and voice.
A soul is loaded as `~/.hermes/SOUL.md` (default profile) or `~/.hermes/profiles/<agent>/SOUL.md`.

These were distilled from shipped, battle-tested production souls, then stripped of
operator-specific facts. Each ends with an **`## Operating notes (FILL PER AGENT)`** section —
that's where *your* specifics go (channels, hosts, repos, named backups). The body above it is
deliberately free of literal paths, IDs, and magic numbers.

## The archetypes

| File | Role | Non-negotiable core |
|---|---|---|
| `SOUL.researcher.md` | Deep research | Claims traced to sources; confidence stated honestly |
| `SOUL.writer.md` | Long-form writing | Voice + structure over volume; no AI slop |
| `SOUL.code-reviewer.md` | Code review | Find the bug class, not the instance |
| `SOUL.qa.md` | QA / verification | Black-box, adversarial, certifies only what it saw run |
| `SOUL.devops-sre.md` | DevOps / SRE | Reversibility first; boring beats clever |
| `SOUL.backend-architect.md` | Backend architecture | Contracts + failure modes before code |
| `SOUL.frontend-designer.md` | Frontend / design | The user's outcome, not the mockup |
| `SOUL.security-auditor.md` | Security audit | Assume breach; prove exploitability, don't speculate |
| `SOUL.data-analyst.md` | Data analysis | Numbers reconcile or they don't ship |
| `SOUL.product-manager.md` | Product | Ruthless scoping; the cut list is a deliverable |

## How to write your own (the short version)

1. **Start from the closest archetype** — don't write from first principles. Copy it, read it end
   to end, delete what doesn't apply.
2. **Identity ≠ config.** The soul holds *stable identity*: role, values, the delegate-vs-do rule,
   safety gates, voice. Anything that drifts (IPs, channel IDs, model names) goes in the Operating
   notes tail or — better — in a skill the soul *points to*. Rule of thumb: no literal path,
   channel ID, or magic number above the Operating notes line.
3. **Name the autonomy gate explicitly.** The strongest pattern we've found: autonomous on
   everything *reversible*, with a **small, named** ask-first set keyed to irreversibility and
   privilege (e.g. "harness config + gateway restarts"). A vague "be careful" gate produces either
   a timid agent or a reckless one.
4. **Make verification a value, not a step.** "A green you didn't verify is not a valid output"
   belongs in the soul, because it survives every context compaction. Proxy signals (exit 0,
   HTTP 200) are not outcomes.
5. **One precedence rule per tension.** Where values collide (completeness vs. minimalism, speed
   vs. cost, autonomy vs. ask-first), write down *which key resolves it* — don't leave it to vibes.
6. **Grounded beats generic.** The best souls encode the corrections your operator actually made
   over weeks of working together. When you catch yourself being corrected twice for the same
   thing, that correction belongs in the soul (or a skill it points to).
7. **Gate changes to it.** Soul edits should be propose → operator approves → snapshot the prior
   version → apply. Keep dated snapshots; you will want the rollback.

## License

MIT-0, same as the rest of this repo. Use them, fork them, ship them.

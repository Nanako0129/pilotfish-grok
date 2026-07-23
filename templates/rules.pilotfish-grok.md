<!-- pilotfish-grok:begin -->
<!-- pilotfish-grok v1.0.4 -->
## Orchestration

### Non-negotiable native Plan gate

For every large, ambiguous, architectural, risky, or explicitly plan-first
task, native Grok Plan Mode and a fresh `plan-verifier` readiness pass are
mandatory. If Plan Mode is not already active, the first tool call MUST be
`enter_plan_mode`, before repository discovery or implementation. If the user
already activated Plan Mode with `/plan`, continue there; the verifier gate
still applies. If `enter_plan_mode` is denied or unavailable, stop without
source writes or implementation tools and ask the user to enter Plan Mode.

Inside Plan Mode, discovery is read-only and the only permitted write is the
session `plan.md`. The main session must synthesize the complete Plan, then
spawn a fresh `plan-verifier` with `background: false`, the exact target
readiness-unit ID and kind, the full Plan text, and relevant evidence paths.
The child must use its installed read-only capability and review exactly that
unit. `READY` is the bare word and nothing else. `REVISE` contains one or more
blockers, each with `Blocker:`, `Evidence:`, `Minimum revision:`, and
`Acceptance check:`. Malformed output is a protocol failure, not a Plan
judgment.

For long or large work, keep shared outcome, non-goals, scope, architecture,
security, dependencies, integration, budget, and stops in one program envelope.
Split execution only into genuinely independent slices with stable IDs,
outcome, scope, non-goals, exclusive owners, prerequisites, acceptance that
proves the slice outcome, and rollback. Review the envelope first, then only the
next executable slice. Once both are `READY`, present them for approval; do not
pre-review unrelated downstream slices. Shared blockers and unmet prerequisites
still gate dependent work. For initial approval, fully specify only the next
executable slice; keep later slices to stable IDs, outcomes, and prerequisites
until they become current.

On `REVISE`, the main session materially revises that unit and sends it to a
fresh `plan-verifier`. After two automatic `REVISE` verdicts for the same unit,
pause it and ask the user how to proceed. The cap is not `READY`, cosmetic
splitting cannot reset it, and user-directed continuation remains allowed.
Only `READY` verdicts for every required readiness unit—the envelope and
current slice for large work—permit `exit_plan_mode`, which presents that
verified scope for user approval. This readiness gate applies to every native
Plan Mode session, including user-initiated `/plan` sessions.

Source writes and implementation tool calls remain prohibited until the user
explicitly approves the verified Plan in a later interaction. A broad initial
request, or a request to skip planning, skip approval, start immediately, or
continue until files change, does not waive this gate. Automatic permission
grants, including always-approve or `bypassPermissions`, are not user approval
of the Plan; an unattended run must stop after presenting the verified Plan.

Main-session policy for Grok Build. If you are running as a subagent role
(`scout`, `plan-verifier`, `security-reviewer`, `mech-executor`, `executor`,
`verifier`, or `security-executor`), ignore this section and complete the task
yourself without further delegation.

Use the named role agents for bounded discovery, execution, and fresh-context
verification while keeping task framing, Plan synthesis, architecture,
ambiguity resolution, integration, and final judgment in the main session.
Complete small, local, already-stable work directly.

| Role | Boundary |
|---|---|
| `scout` | Broad or focused read-only repository reconnaissance |
| `plan-verifier` | Pre-approval Plan challenge; `READY` or `REVISE` |
| `security-reviewer` | Pre-approval read-only security evidence |
| `mech-executor` | Fully specified mechanical implementation |
| `executor` | Bounded implementation requiring local judgment |
| `verifier` | Completed-work challenge; `CONFIRMED` or `REFUTED` |
| `security-executor` | Approved security-sensitive implementation |

There is no installed `Explore` role. Use `scout` for discovery. Grok's built-in
`explore` type may still be used for broad searches when useful; do not treat it
as a pilotfish-grok named role with custom routing.

For large, ambiguous, architectural, risky, or explicitly plan-first work, use
this lifecycle:

| Phase | Gate | Eligible delegation |
|---|---|---|
| Discovery | Enter native Plan Mode first for gated work, then stabilize the question, allowed scope, evidence format, and stop condition with read-only discovery. The final implementation may remain unknown. | Bounded read-only `scout` work on disjoint evidence surfaces. |
| Plan | The main session writes one `plan.md` containing outcome, non-goals, scope, a program envelope, and independent slices. | Mandatory fresh read-only `plan-verifier` reviews the envelope, then the next executable slice; structured `REVISE` returns ownership to the main session. |
| Approval | `READY` for the envelope and current slice unlocks `exit_plan_mode` to present that scope and wait for explicit user approval. | Read-only clarification only; do not send an implementation brief or edit source before required approval. Parent Plan Mode does **not** replace read-only capability on child agents. |
| Execution | The authorized contract has stable scope, exclusive ownership, constraints, done criteria, integration, and verification. | `mech-executor`, `executor`, or `security-executor`, chosen by the contract and trust boundary. |
| Verification | The integrated result is concrete enough to refute as a completed-work claim. | A fresh `verifier` returns only `CONFIRMED` or `REFUTED`. |

### Dispatch

Before every `spawn_subagent` call, identify the phase and apply a dispatch
brake. Do not fan out when workers would repeatedly depend on evolving shared
evidence, write ownership overlaps, no clear synthesis or integration owner
exists, or coordination cost exceeds the likely benefit. Discovery agents report
facts; the main session reconciles contradictions and writes the Plan.

Use the smallest useful execution shape: work directly for small or tightly
coupled tasks, one worker for a bounded side task, and bounded parallel workers
only for independent, low-overlap workstreams. Delegate only when the saved
execution or context cost exceeds the briefing, coordination, and review cost.
A matching role makes work eligible rather than mandatory.

The mandatory `plan-verifier` readiness gate is not an optional delegation
choice and is not waived by the dispatch brake or coordination-cost heuristic.

A delegation-planning layer may shape discovery questions, execution topology,
worker count, ownership, sequence, budgets, and stop conditions. This policy
remains authoritative for named role semantics, the leaf-agent boundary, the
approval gate, and verifier contracts. Role TOMLs and agent definitions remain
authoritative for capability mode and reasoning-effort bindings; optional
`[subagents.models]` pins own model routing.

Keep a single unknown bug's initial root-cause discovery, trace-driven
debugging, tightly coupled state propagation, and the first minimal fix in the
main session when they share one reasoning chain. Use a scout only for a
bounded side question whose result does not own or block the main diagnosis.

Route security-sensitive work through separate capability boundaries. Before
the first readiness review for an affected unit, finish `security-reviewer` and
carry its findings and dispositions into the Plan; do not run the two reviews
concurrently. After approval, give the stable implementation contract to
`security-executor`.

### Routing ownership

Model and capability routing is owned by the named agent and role definitions.
When spawning a named role via `spawn_subagent`, omit invocation-level `model`
and `capability_mode` overrides so the installed defaults apply. Use an ad-hoc
override only for a truly ad-hoc agent with no matching role definition.

Brief each worker in one shot with the goal, constraints, done criteria,
relevant paths, rationale, output format, budget, and verification expectation.
Start with the cheapest eligible role. After two failed attempts, change the
task boundary, escalate one tier, or take over. Treat scout findings as inputs;
sanity-check any single fact that carries a decision.

### Parallelism and long work

Schedule by data dependency. Start independent agents with `background: true`
when useful, give writing agents exclusive file ownership or
`isolation: "worktree"`, continue independent main-session work while they run,
and collect every result with `get_command_or_subagent_output` before dependent
work or the final answer. Uncollected worktrees are lost work.

Long-running processes belong to the main session. Leaf agents must not detach
them; they return the exact command, absolute working directory or worktree,
required environment, input paths, and completion criterion so the orchestrator
can run them with `run_terminal_command` (`background: true` when needed) and
re-task the leaf with the captured result.

Never swap `plan-verifier` and `verifier`. The former challenges Plan readiness
with `READY` / `REVISE`; the latter reproduces tests and challenges a
completed-work claim with `CONFIRMED` / `REFUTED`. Neither role writes the Plan
or fixes findings. After a concrete `REFUTED`, materially fix the same claim
before using a fresh verifier. After two consecutive `REFUTED` verdicts for
that claim, stop automatic fix-and-reverify cycling and surface the failures
and options to the user; the cap is not `CONFIRMED`, and user-directed
continuation remains allowed. Do not reverify a substantially unchanged
implementation. Final judgment remains in the main session.
<!-- pilotfish-grok:end -->

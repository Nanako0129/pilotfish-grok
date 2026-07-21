<!-- pilotfish-grok:begin -->
<!-- pilotfish-grok v1.0.2 -->
## Orchestration

### Non-negotiable approval gate

For every large, architectural, risky, or explicitly plan-first task, source
writes and implementation tool calls are prohibited until the main session has
presented a Plan and received explicit approval in a separate later user turn.
A request to skip planning, skip approval, start immediately, or continue until
files change does not waive this gate. On that first turn, present the Plan and
stop without editing.

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
| Discovery | Stabilize the question, allowed scope, evidence format, and stop condition. The final implementation may remain unknown. | Bounded read-only `scout` work on disjoint evidence surfaces. |
| Plan | The main session synthesizes one Plan containing outcome, non-goals, scope, dependencies, exclusive ownership, sequence, verification, budgets, and stop conditions. | A fresh `plan-verifier` may challenge readiness and return only `READY` or `REVISE`. |
| Approval | Present the Plan and wait for explicit user approval when the work is large, architectural, risky, or explicitly plan-first. | Read-only clarification only; do not send an implementation brief or edit source before required approval. For Grok, `enter_plan_mode` may enforce a parent edit gate, but it does **not** replace read-only capability on child agents. |
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
required approval, use `security-reviewer` for evidence only. After approval,
give the stable implementation contract to `security-executor`.

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
or fixes findings. Final judgment remains in the main session.
<!-- pilotfish-grok:end -->

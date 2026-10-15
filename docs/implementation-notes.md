# Technical implementation notes

Technical rationale and original high-level build sequence. For authoritative feature status, dependencies, acceptance criteria and session handoff, use the [implementation tracker](implementation-plan.md). The five increments below are a conceptual summary, not a second progress tracker.

## Recommended stack

Deploy the Python project as Linux containers managed by Docker Compose. Docker is the required runtime target from the first implementation milestone, with application dependencies installed inside images. See [container deployment](container-deployment.md) for the service topology and operational contract. Start with a CLI and recorded-data replay, then add market connectivity and a local status interface. Keep infrastructure small enough that a complete decision can be traced from input event through broker acknowledgement.

| Area | Recommendation | Reason |
|---|---|---|
| Language | Python, isolated project environment and committed dependency lock | Reuse the current analysis code and support numerical/model-based plugins |
| Python version | Select a minor version after testing the cTrader SDK, Twisted, protobuf and validation stack together | Workspace Python is currently 3.14.7; this is an observation, not a compatibility guarantee |
| Contracts | Pydantic strict models at boundaries; dataclasses/protocols inside modules; Decimal prices and money | Reject malformed decisions and make units explicit |
| Core scheduling | asyncio with bounded queues and explicit event cursors | Manage concurrent feeds and evaluations without losing order |
| Strategies | Explicit package registry and Python Protocol; one worker container per active instance initially | Replaceable strategies, isolated failures and bounded evaluation time |
| Broker | Separate gateway using official cTrader Open API Python SDK over TLS/TCP | Integrate streaming and execution while isolating SDK networking |
| Operational state | SQLite WAL on local disk, one core writer, transactional event/outbox tables | Durable ordering, reservations and restart recovery with modest operations |
| Evidence | Immutable compressed JSON snapshots initially; partitioned columnar data later if tick volume warrants it | Preserve exact decisions without placing unlimited tick history in operational tables |
| Tests | pytest plus property-based tests for state/risk invariants; recorded broker fixtures | Verify causality, rounding, retries and crash recovery |
| UI | Read-only local status page after the CLI works; later explicit authenticated control endpoints | Keep UI availability independent of execution |
| Deployment | Docker Compose on Docker Desktop for development/shadow; Docker Engine on an always-on Linux host for sustained operation | Avoid laptop sleep becoming a trading-runtime dependency |

Pydantic strict mode reduces implicit type coercion, but JSON parsing has type-specific exceptions. Explicitly validate finite decimals, UTC timestamps, units and semantic invariants. [Official documentation](https://docs.pydantic.dev/latest/concepts/strict_mode/).

The official cTrader SDK uses Twisted. Run it in the gateway's own process and keep asyncio in the core, rather than maintaining two event loops inside the same process. The documented Python SDK transport supports TCP rather than WebSocket. [SDK documentation](https://help.ctrader.com/open-api/python-SDK/python-sdk-index/), [connection documentation](https://help.ctrader.com/open-api/connection/).

SQLite WAL supports concurrent readers but a single writer at a time and requires same-host shared-memory access. Keep the operational database on local disk; the UI receives status through the core or reads through a controlled read-only connection. Use the SQLite backup API for consistent backups. Move to PostgreSQL only when measured load or multi-host requirements justify it. [SQLite WAL documentation](https://www.sqlite.org/wal.html).

## Process and transaction boundaries

**Core process:** registry, scheduler, evidence validation, account arbiter, risk controller, order state machine, persistence and outbox. It alone writes the operational database. Strategies receive read-only snapshots, never direct database connections.

**Strategy workers:** run in separate containers and receive bounded typed messages over authenticated internal TCP connections, returning typed evaluations. Use length-framed JSON messages and Compose service DNS; no shared Unix sockets or host paths are required. Include message/schema version, sequence ID, instance ID, deadline and maximum payload size. Do not use pickle for plugin-origin messages. Process isolation limits crashes, not malicious Python code; install reviewed packages only and use OS/container isolation before accepting untrusted code.

**Broker gateway:** owns broker credentials and the authenticated connection. It normalizes inbound market/execution events and transmits commands created by the core. No strategy can invoke it directly. Enforce one gateway/account writer and a core-session fencing token; reject stale control sessions. A lost core connection prevents new submissions. Retain server-side protection on established positions.

Commit decision, next strategy state, consumed-event cursor and intent in one database transaction. Commit risk reservation and outbox command together in another serialized transaction after account checks. The executor marks an attempt before handing it to the gateway. A missing acknowledgement creates an unknown outcome that must be reconciled; transport retries must not blindly resubmit orders. Exactly-once network delivery is not assumed.

Use unique database constraints on event consumption, instance decision ID, command ID and broker event identity. Reserve risk using an immediate transaction and recompute the aggregate inside that transaction. Durable outbox replay distinguishes unsent commands from attempts whose delivery is uncertain.

Bound all queues. Never silently drop execution events or required strategy input: overflow inhibits affected entries and invokes backfill/reconciliation. Lossy quote coalescing is allowed only for consumers whose declared semantics permit it; tick-sensitive strategies require complete ordered coverage or an unavailable result.

**Supervisor:** checks application heartbeat and reconciliation progress and can inhibit entries. Docker restart policies recover exited containers; application health failures alone do not imply automatic restarts. The supervisor has no Docker socket access; a supervisor restart does not clear risk limits. A competing recovery process must never become a second broker writer.

## Code layout to implement

```text
autonomous-trading/
  README.md
  docs/
  compose.yaml                   # default offline/paper deployment
  compose.demo.yaml              # explicit broker/account binding
  compose.live.yaml              # explicit live deployment overrides
  Dockerfile                     # core/worker/gateway build targets
  .dockerignore
  pyproject.toml                 # create when compatibility spike selects dependencies
  config/
    accounts/                   # aliases and policy, no secrets
    instances/                  # strategy bindings, mode, universe and profiles
  src/trading_platform/
    contracts/                  # event, snapshot, decision and order schemas
    registry/                   # package loading and capability checks
    runtime/                    # scheduling, worker IPC and event cursors
    market_data/                # normalization, history and completeness checks
    portfolio/                  # allocation, ownership and conflict policies
    risk/                       # risk model interface, limits and reservations
    execution/                  # planner, order lifecycle and durable outbox
    persistence/                # migrations, repositories and backup
    gateways/ctrader/           # official SDK integration
    strategies/tpr1/            # first adapter, not imported by shared core
    simulation/                 # replay clock, fills and fault injection
    observability/              # structured logs, metrics and health
    cli.py
  tests/
    contract/
    replay/
    risk/
    execution/
    broker/
  var/                          # ignored runtime data; separate by account and mode
```

The repository now includes module boundaries, an offline validation CLI, Dockerfile, Compose validation/tests and CI. The tree above remains the full runtime target; demo/live overrides and trading services are not implemented.

## Build in five deliverable increments

| Increment | Concrete output | Completion gate |
|---|---|---|
| 1. Contract and replay kernel | Docker build/Compose startup and CI smoke test; typed schemas, registry, event clock, isolated worker, SQLite event/state persistence; TPR adapter and unrelated timer fixture | Both packages load by configuration without core edits; TPR baseline matches; replay and restart preserve state |
| 2. Account risk and paper execution | Ownership, allocations, concurrent reservations, order planner, paper broker and outbox | Conflicting proposals cannot exceed limits; duplicate events and timeout-after-acceptance do not duplicate orders |
| 3. Read-only cTrader gateway | Auth lifecycle, quote subscriptions, history, account metadata and broker reconciliation | Actual provider evidence meets the declared data contract; unknown fields remain unknown; units and currency valuation verified |
| 4. Autonomous demo lifecycle | Submission, fills, cancellation, protection, expiry and emergency recovery | Tested partial fills, cancel/fill races, reconnects, rejection, missing protection and account mismatch |
| 5. Operations and evaluation | Status page, alerts, deployment service, backup/restore and per-strategy/portfolio evaluation | Restart drills pass; operating mandate selected; execution reliability and performance evidence reviewed before live deployment |

Begin the SDK compatibility and metadata feasibility spike early alongside increment 1; a missing mandatory provider capability must not be discovered after building the complete executor. No trading credentials are needed for the replay kernel or simulated broker. Real connectivity will require an Open API application registration, account authorization and explicit demo/live account binding. Do not read or copy credentials from unrelated projects.

Proposed CLI surface: `validate-instance`, `replay`, `run --mode shadow`, `status`, `pause-entries`, `resume-after-checks`, and `flatten-owned-and-halt`. These are future commands, not runnable instructions today. Demo/live binaries must reject missing or mismatched account bindings and cannot infer mode from whichever account happens to be active in a desktop application.

## How a new strategy is supplied

Accept an executable package plus manifest and instance configuration. If supplied as a natural-language skill, first translate it into an explicit specification with examples and expected decisions, then implement a plugin or a structured model-backed evaluator. Resolve undefined entry/exit rules before executable deployment. The platform must not reinterpret strategy prose differently on every evaluation.

An AI-backed plugin can call a platform-managed model service and return the same decision schema as deterministic code. Record input, output, model/prompt versions, latency and cost. A missing/late answer means no new trade. Strategy-specific indicators, models and dependencies stay inside the plugin. Risk and order submission remain deterministic shared services.

For the first build, use TPR-1 to prove compatibility and a synthetic H1/timer strategy to prove independence. The second fixture need not be profitable or connected to a real account; its job is to fail any accidental M1/TP1/2R coupling.

## Operational acceptance

Observe feed age, finalized-bar lag, evaluation latency, queue depth, unknown broker outcomes, protection status, reserved risk, drawdown and per-instance health. Every trade must link to a decision and immutable evidence. Alerts should identify action required rather than report every no-trade minute.

Pin dependency versions after a clean-environment compatibility test, keep database migrations versioned, and rehearse restoring a backup followed by broker reconciliation before resuming entries. Do not place live database files in cloud-sync folders or shared network volumes.

The recommended first implementation commitment is increments 1 and 2: a working strategy-independent engine with deterministic replay and paper execution. This establishes the architecture's behavior before broker-side side effects are introduced.

# Implementation tracker and session handoff

Last updated: 2026-10-15. Repository: `chukkilala007/autonomous-day-trading-sys`.

This is the go-to document for **what exists, what comes next, how to implement it, and how to resume after context is lost**. Feature status here is authoritative; architecture documents describe intended behavior, not delivered functionality. Update this file in the same change as the implementation it tracks.

## Current handoff — start here

| Item | Current value |
|---|---|
| Verified implementation baseline | `578b26a145db099bc11252169ebad3fb0e6c8896` — scaffold, Docker validation and CI definition |
| Completed stage | S0: repository scaffold |
| Current implementation work | Sequential feature implementation through S4 |
| Next feature | F1.3 |
| Next concrete action | Implement and verify F1.3 using its feature branch and acceptance criteria |
| Next milestone | S1 gate: tested typed contracts, configuration and package registry |
| Working branch policy | One feature/<feature_name> branch from develop; test, commit, merge --no-ff to develop |
| Trading state | No broker integration, credentials, open-trade management or live execution in this implementation |
| External inputs | TPR source/provenance needed at F3.1; broker application/account authorization needed at F5.1; neither blocks F1.1 |
| Known limitations | Module directories mostly contain placeholder docstrings; example strategy is not installed; no persistent runtime exists |
| Verification evidence | Scaffold session: Compose config, Docker validation, and four unit tests locally/in Docker passed. GitHub-hosted CI outcome has not been inspected |
| Uncommitted implementation | None at tracker creation; inspect `git status` on every resumption |

The tracker-writing commit is documentation work, not a new runtime milestone. Future handoffs must name the active feature, changes already made, exact failing/passing checks, unresolved decisions, and the next action. Never leave “continue implementation” as the only next step.

## Resume procedure

1. Read this handoff, then inspect `git status --short --branch` and `git log -5 --oneline`. Preserve unrelated local edits. Do not reset to the baseline commit above.
2. Inspect the active feature's actual source and tests. If code and tracker disagree, record the discrepancy and establish evidence before changing status.
3. Read the relevant contracts and decision records. Select one eligible feature; mark it IN_PROGRESS with date and owner/session label.
4. Implement a narrow vertical slice. Add tests that exercise behavior and failure cases, then run the feature's checks in the container where applicable.
5. Update status, evidence, remaining work and handoff in this document. Update public instructions if CLI, deployment or behavior changed.
6. Commit/push according to the user's current instructions and record the reference. Do not claim a push, CI pass or deployment without observing it.

Commands available **now**, from repository root:

```sh
git status --short --branch
git log -5 --oneline
docker compose config --quiet
docker compose up --build --abort-on-container-exit --exit-code-from validate
docker compose --profile tools run --rm tests
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The Compose `validate` service currently checks example configuration and exits. It is not a paper-trading runtime. Commands described in future features are proposed until implemented and documented.

## Status and completion rules

Statuses: **TODO**, **IN_PROGRESS**, **BLOCKED**, **DONE**, **DEFERRED**. BLOCKED must identify the missing dependency/input and a concrete unblock action. DEFERRED must identify why it is outside the current release. An unchecked task is not implicitly in progress.

Each feature below specifies scope, likely code locations, dependencies and acceptance checks. File names are implementation targets, not claims those files exist. A feature should be small enough for one focused implementation/review cycle; split it into F1.1a/F1.1b if that is no longer true.

A feature is DONE only when its acceptance checks pass, container behavior is verified where relevant, operational limitations are documented, and evidence is recorded. The entire stage remains open until its integration gate passes. No percentage-complete claims based on directory count or lines of code.

For completed work, add an entry to the Delivery ledger containing feature ID, date, commit/PR, changed behavior, checks with results, and limitations. If updating in the same commit, use “this change” and resolve the commit reference in a subsequent update; do not fabricate a self-referential hash.

## Fixed design boundaries

* Strategies are replaceable versioned packages. TPR-1 is the first adapter, not a core rule set. Core has no hardcoded M1/TP1/2R logic.
* Docker Compose on one host is the initial deployment model; one core database writer and one fenced broker gateway per account.
* Strategies propose; account policy decides eligibility and allocation; the executor is the only order authority.
* SQLite local named-volume state and transactional outbox initially. No shared network filesystem or active-active trading failover.
* Default mode is offline/paper. Shadow means real market observation with **zero order submission**. Demo and live are separate account-bound deployment modes.
* Unknown data, outcome or ownership is preserved as unknown. Broker events establish fills; candle touches do not.
* No blind order retries, no credential/model access from arbitrary strategy code, and no self-increase of risk limits.
* Initial execution capability is single-instrument directional trades with verified protective stops. Other capabilities require their own tracked extension.

References: [architecture](autonomous-scalping-agent.md), [strategy interface](strategy-contract.md), [container requirements](container-deployment.md), [technical implementation notes](implementation-notes.md). Policy numbers in those documents are proposals, not activated account mandates.

## Stage map

| Stage | Outcome | Status | Gate |
|---|---|---|---|
| S0 | Repository and offline container scaffold | DONE | Existing four tests and container validation pass |
| S1 | Contracts, configuration, registry and reproducible toolchain | TODO | Valid/invalid package and proposal fixtures behave consistently inside Docker |
| S2 | Durable event processing and isolated workers | TODO | Crash/replay preserves state without cross-instance contamination |
| S3 | Strategy adapters and causal replay | TODO | TPR parity plus unrelated fixture proves strategy independence |
| S4 | Portfolio risk and autonomous paper lifecycle | TODO | Two strategies share risk and recover safely from simulated failures |
| S5 | Verified broker data and read-only shadow runtime | TODO | Provider contract evidenced; no execution path enabled |
| S6 | Autonomous demo order lifecycle | TODO | End-to-end demo and fault suite pass with reconciled exposure |
| S7 | Operable release: controls, deployment and recovery | TODO | Restore/restart/upgrade drills and dashboard evidence complete |
| S8 | Evaluation and controlled live release | TODO | Evidence and explicit deployment mandate recorded |
| S9 | Optional model-backed strategy support | DEFERRED | Added only after deterministic runtime is established |

Primary dependency chain: S1 → S2 → S3 → S4 → S6 → S7 → S8. S5 follows S2 and its provider feasibility can start earlier; S6 also requires S5. Read-only metrics and health primitives are implemented with their owning components, not delayed until S7. The production UI and drills are consolidated in S7.

## S0 — verified scaffold

### F0.1 — Repository, documentation and offline checks — DONE

**Delivered:** package/module layout, architecture/contract/container documents, Dockerfile, Compose validation/test services, example paper instance, CLI status/config-shape validation, four unittest cases and a GitHub Actions workflow. Existing license/history preserved.

**Evidence:** baseline commit `578b26a`; `src/trading_platform/cli.py`, `tests/test_config.py`, root Docker/Compose files and `.github/workflows/ci.yml`. Local/container tests and Docker validation passed during scaffold creation.

**Limits:** no dependency lock, digest-pinned image, strategy loader, broker, persistence, simulated fills or service daemon. CI is configured; remote execution result is not established here.

## S1 — contracts and package loading

### F1.1 — Toolchain, dependencies and container test baseline — DONE

**Depends on:** F0.1. **Code:** `pyproject.toml`, lockfile, `Dockerfile`, CI, `docs/decisions/`.

**Tasks:** confirm Python minor compatibility with Pydantic, pytest/property-test tools and the cTrader/Twisted/protobuf stack; select and record the lock mechanism; separate core/test/gateway dependencies; pin the base image digest and CI action revisions; install the package in the image rather than relying solely on PYTHONPATH; preserve an offline test target.

**Accept:** clean image build resolves the lock without drift; package CLI works from its installed entry point; tests run with no broker secrets; CI exercises the same image path. Record which CPU architectures were actually tested. Provider account access is not required for dependency import checks.

### F1.2 — Shared value and event contracts — DONE

**Depends on:** F1.1. **Code:** `contracts/values.py`, `events.py`, `snapshots.py`; `tests/contract/`.

**Tasks:** define finite Decimal prices/quantities/money with currency and units; UTC source/receipt/availability times; account/environment/instrument identities; immutable quote/bar/snapshot records; versioned event envelopes and canonical serialization/hashes.

**Accept:** reject nonfinite values, naive timestamps, malformed OHLC and unit/basis omissions; source time cannot be replaced by receipt time; serialization round trips without float loss; identical canonical input produces identical identity. Test publication-time causality for non-price inputs.

### F1.3 — Decision, proposal and management contracts — TODO

**Depends on:** F1.2. **Code:** `contracts/decisions.py`, `orders.py`, `capabilities.py`.

**Tasks:** discriminated NO_ACTION/WATCH/ENTRY/MANAGEMENT/UNAVAILABLE envelopes; separate market/limit/stop proposal schemas; ownership, expiry, preconditions and state revisions; generic protection/exit specification; namespaced strategy diagnostics and stable action IDs.

**Accept:** market entry without TP1 is representable under an appropriate profile; incomplete executable proposals fail; one strategy cannot name an unowned management target; do not impose 2R or TPR states globally. Cover stale deadlines and invalid amendment revisions.

### F1.4 — Configuration and deployment mandate validation — TODO

**Depends on:** F1.3. **Code:** `contracts/config.py`, `config/`, `cli.py`.

**Tasks:** versioned instance, account-policy, risk/execution profile schemas; paper/shadow/demo/live mode semantics; explicit account aliases and immutable config hash; secret references without secret values; replace or clearly deprecate scaffold `validate-config` with `validate-instance`.

**Accept:** unknown/contradictory fields rejected; demo/live require matching configured environment and account binding; shadow has no submission capability; per-strategy budgets cannot exceed account policy. Tests must not require real credentials.

### F1.5 — Registry and plugin protocol — TODO

**Depends on:** F1.4. **Code:** `registry/loader.py`, `manifest.py`, `contracts/strategy.py`.

**Tasks:** reviewed package allowlist, digest/version checks, manifest requirements and capabilities, initialize/evaluate/validate/migrate hooks; distinguish package from instance; instance state namespace; dependency compatibility checks.

**Accept:** two fixture packages load through configuration without core edits; malformed manifest, digest mismatch, duplicate instance and unsupported capability fail with actionable reasons; common modules cannot import concrete strategy packages. Add an architecture dependency check to CI.

**S1 gate:** F1.1–F1.5 DONE; versioned input and decision fixtures pass through package loading and validation inside the container. No broker commands exist yet.

## S2 — durable runtime and worker isolation

### F2.1 — Database schema and migration boundary — TODO

**Depends on:** F1.3. **Code:** `persistence/database.py`, `migrations/`, `repositories.py`.

**Tasks:** schema-version tracking; tables for events/cursors, snapshots, instance states, decisions/intents, reservations, commands/attempts, broker entities, account checkpoints and halts; unique constraints; WAL configuration and one-writer enforcement; local named-volume ownership.

**Accept:** migrations work on empty and prior-version fixtures; conflicting writer startup fails; restart retains state; rollback after an injected transaction failure leaves no half-written decision. Backups use SQLite APIs, not a live-file copy.

### F2.2 — Event journal and atomic evaluation commits — TODO

**Depends on:** F2.1, F1.5. **Code:** `runtime/journal.py`, `persistence/events.py`, `snapshots.py`.

**Tasks:** journal accepted inputs; commit consumed cursor, next state and decisions together; immutable evidence storage/reference/hash; revision records; idempotent event ingestion; distinguish processing order from market source time.

**Accept:** crash before/after commit yields either old or complete new state; duplicate delivery cannot duplicate decisions; evidence hash mismatch blocks use; replay cursor never skips unprocessed events. Retain earlier evidence when provider revisions arrive.

### F2.3 — Causal scheduler and virtual clock — TODO

**Depends on:** F2.2. **Code:** `runtime/scheduler.py`, `clock.py`, `simulation/clock.py`.

**Tasks:** bar/tick/timer/execution subscriptions; bounded per-instance queues; explicit deadline/watermark policies; multi-instrument as-of views; virtual time for replay; backpressure and gap signals.

**Accept:** no future bar or unpublished feature reaches an evaluation; deterministic event ordering; queue overflow blocks rather than silently loses required data; stopped/closed sessions do not fabricate bars. One blocked instance does not starve unrelated instances.

### F2.4 — Authenticated container worker transport — TODO

**Depends on:** F2.3. **Code:** `runtime/worker.py`, `transport.py`, Docker targets and Compose networks.

**Tasks:** bounded length-framed JSON, role/instance authentication, handshake schema versions, request IDs, timeouts and heartbeats; one worker container per instance; core supplies state and read-only snapshots; no strategy database/secret mounts.

**Accept:** oversized/malformed/unauthenticated messages rejected; stale response cannot update current state; worker timeout/crash inhibits its entries; worker cannot directly reach broker control; denied-network and secret-mount checks pass. Do not claim arbitrary hostile Python is fully sandboxed.

### F2.5 — Recovery state and instance replacement — TODO

**Depends on:** F2.4. **Code:** `runtime/recovery.py`, `registry/lifecycle.py`.

**Tasks:** BOOTING/WARMING/READY/DEGRADED/HALTED lifecycle; persistent halt reasons; initialization/replay on restart; explicit state migrations; drain-and-replace behavior that retains old version ownership for unresolved orders/positions.

**Accept:** restart does not clear a halt; unavailable state migration fails explicitly; duplicate instance registration rejected; replacement cannot adopt another version's exposure silently. Use synthetic owned-position fixtures until real execution exists.

**S2 gate:** restart core and one worker during evaluation, replay the journal and reproduce the same committed decisions with isolated state. Gate evidence includes container logs and state assertions.

## S3 — strategy adapters and causal replay

### F3.1 — TPR baseline provenance and portability — TODO

**Depends on:** F1.5. **Code:** `strategies/tpr1/`, `tests/fixtures/tpr1/`, provenance manifest.

**Tasks:** obtain reviewed existing helper and reference rules from the original workspace; record source/version/hashes and licensing suitability; package only required code and sanitized synthetic fixtures; identify strategy-specific versus generic validation. No personal paths or account snapshots in runtime imports.

**Accept:** baseline imports in a clean container; provenance identifies exact source; fixtures contain no secrets/account identifiers; old monitor state is never migrated into execution state. If source is unavailable, mark this feature BLOCKED while the unrelated fixture proceeds.

### F3.2 — TPR strategy adapter and parity suite — TODO

**Depends on:** F3.1, F2.3. **Code:** `strategies/tpr1/adapter.py`, `manifest.*`, `tests/replay/test_tpr_parity.py`.

**Tasks:** wrap helper into generic protocol; package M1/M5/context requirements and parameters; map candidate events into common decisions; keep TPR-specific geometry/cost rules in its validator/profile; separate research touches from confirmed execution events.

**Accept:** original baseline and adapter agree on candidate IDs, anchors, timing, reasons and geometry; causal pivots, target retirement, missing context and pending expiry tests pass; future bars do not alter earlier decisions. No unexplained parity differences accepted.

### F3.3 — Independent timer/H1 fixture strategy — TODO

**Depends on:** F1.5, F2.3. **Code:** `strategies/timer_fixture/`, fixture configuration/tests.

**Tasks:** deterministic synthetic strategy using H1/timer events, a market-entry proposal, protective stop and timed exit; explicitly label it an architecture fixture, not a production strategy.

**Accept:** no M1/TP1/2R requirement; package loads without touching core; separate instance state; management proposals use owned broker-view fixtures. Tests fail if TPR assumptions leak into shared code.

### F3.4 — Replay CLI and evidence reports — TODO

**Depends on:** F3.2, F3.3, F2.5. **Code:** `simulation/replay.py`, `market_data/history.py`, `cli.py`.

**Tasks:** normalized recorded-data loader, duplicates/gaps/revisions policy, causal clock, immutable run/config manifest, decision/reason summaries and reproducibility comparison. Replay mode is isolated from runtime volumes and broker endpoints.

**Accept:** both strategies replay using identical infrastructure; deterministic rerun matches; conflicting history revisions fail visibly; source quotes are not backdated; missing execution data prevents fabricated P&L. CLI exit codes distinguish valid no-signal output from unavailable input.

**S3 gate:** run both strategies in Docker using configuration-only selection and compare replay output; TPR parity and unrelated fixture pass. This proves architecture compatibility, not market edge.

## S4 — shared risk and autonomous paper trading

### F4.1 — Portfolio ownership and account arbitration — TODO

**Depends on:** F2.1, F1.4. **Code:** `portfolio/ownership.py`, `allocation.py`, `arbiter.py`.

**Tasks:** account/instance attribution, shared pending/open exposure view, exclusive-symbol initial policy, configured priority/time/ID ordering, concentration buckets and external-exposure handling.

**Accept:** simultaneous conflicting intents have deterministic outcomes; one strategy cannot cancel another's trade; unknown external exposure blocks entries; opposite signals are not silently netted; budgets are subdivisions of the account ceiling.

### F4.2 — Risk model interface and stop-based sizing — TODO

**Depends on:** F4.1. **Code:** `risk/models.py`, `sizing.py`, `valuation.py`.

**Tasks:** independently verified unit loss/currency conversion; costs/slippage allowance; minimum/maximum/step rounding down; margin check; risk-profile selection; conservative worst-fill valuation.

**Accept:** Decimal fixtures cover GBP/USD conversion, non-unit volume steps and minimum size over budget; unknown costs/valuation reject; stop never moves to force size; unsupported nonlinear contracts fail instead of using the linear model.

### F4.3 — Atomic reservations and persistent circuit breakers — TODO

**Depends on:** F4.2, F2.2. **Code:** `risk/reservations.py`, `limits.py`.

**Tasks:** serialized budget checks/reservation; pending/partial-fill/in-flight exposure; cash-flow-adjusted equity checkpoints; daily timezone boundary, loss streak and cooldown; distinguish entry blocking from risk-reducing actions.

**Accept:** concurrent attempts cannot oversubscribe; unknown submissions keep reservations; confirmed terminal events release once; restarts/DST/deposits cannot reset or distort limits; close/reduce actions remain possible when entry budget is exhausted.

### F4.4 — Order planner, lifecycle and durable outbox — TODO

**Depends on:** F4.3. **Code:** `execution/planner.py`, `state_machine.py`, `outbox.py`.

**Tasks:** map supported profiles into generic commands; pre-send price/deadline/revision checks; create reservation/outbox atomically; submission attempt journal; ACCEPTED/PART_FILLED/FILLED/CANCEL_PENDING/UNKNOWN/terminal transitions; ownership-based management.

**Accept:** unsupported order semantics fail; duplicate/out-of-order acknowledgements do not regress state; timeout after send creates UNKNOWN, not an automatic retry; no blind release on cancel request; a stale amendment cannot overwrite a fill.

### F4.5 — Paper broker and fault scenarios — TODO

**Depends on:** F4.4, F3.4. **Code:** `simulation/broker.py`, `fills.py`, `faults.py`.

**Tasks:** execution-port implementation driven by contemporaneous bid/ask/ticks; spread/commission/slippage assumptions; stop-limit nonfills/expiry; partial fills; rejection/disconnect/timeout injection; conservative ambiguity outcomes.

**Accept:** no fill at an unavailable price; entry touch alone does not prove a fill; full event lifecycle matches broker contract fixtures; configurable faults reproduce cancel/fill race and accepted-but-unacknowledged submission without duplicates. Unknown costs remain unknown.

### F4.6 — Integrated persistent paper stack — TODO

**Depends on:** F4.5, F2.5. **Code:** Compose services, CLI run/status commands, `tests/execution/` end-to-end suite.

**Tasks:** connect input → workers → risk → executor → paper broker → state; named volumes and status summaries; continuously process owned execution events; simulator replaces real gateway in default mode.

**Accept:** documented single Compose command runs two configured instances; trades and reasons trace to evidence; core/worker/simulator restarts preserve limits and ownership; repeat the fault matrix and show no unexplained exposure. Default stack contains no real broker credentials or reachable order endpoint.

**S4 gate:** complete paper entry/protection/exit plus restart recovery for both strategies. This is the first autonomous trading runtime milestone, entirely simulated.

## S5 — broker feasibility and read-only shadow operation

### F5.1 — cTrader authentication and account binding — TODO

**Depends on:** F1.1, F1.4. **Code:** `gateways/ctrader/client.py`, `auth.py`, gateway image/secret configuration.

**Tasks:** SDK/Twisted process; TLS, heartbeat and reconnect; application/account authentication; mounted secret input and atomic refreshed-token persistence; rate-limited retry/backoff; explicit environment/account identity checks.

**Accept:** demo connection established with authorized credentials; mismatched account fails; logs redact secrets; restart/token-refresh tests preserve credentials safely; execution capability remains disabled. Use fake transport tests when real authorization is unavailable and label live integration unverified.

### F5.2 — Provider capability audit and normalization — TODO

**Depends on:** F5.1, F1.2. **Code:** `gateways/ctrader/metadata.py`, `normalization.py`; provider-evidence report.

**Tasks:** verify protocol price/volume scaling, exact symbols, timestamp semantics, tick grid, candle basis, real session status, contract value, fees, conversion, margin and protection/order capabilities; record provenance and missing fields explicitly.

**Accept:** documented field-by-field evidence and conversion fixtures; no digits-as-tick or schedule-as-live-state inference; unsatisfied mandatory capability blocks execution. If broker-native extension is necessary, create a scoped feature/decision record rather than loosening validation.

### F5.3 — Streaming feed, history and gap repair — TODO

**Depends on:** F5.2, F2.3. **Code:** `market_data/service.py`, `bars.py`, `coverage.py`; gateway subscriptions.

**Tasks:** per-manifest subscriptions/warm-up, shared compatible feeds, finalized bar validation, incremental history overlap, rate limiting, revision audit and reconnect backfill; session-aware missing-interval detection.

**Accept:** no unfinished bars in closed-bar events; missing intervals inhibit relevant decisions; unchanged subscription quote cannot prove an open market; backfill does not resurrect an expired opportunity; multi-instrument snapshots use verified causal coverage.

### F5.4 — Read-only account reconciliation and shadow stack — TODO

**Depends on:** F5.3, F4.6. **Code:** `execution/reconciliation.py`, shadow configuration and Compose override.

**Tasks:** ingest balances, pending orders, positions and deals without mutations; account health/exposure view; real-feed decisions and paper projections in separately labelled storage; assert no order-write path in shadow mode.

**Accept:** cold start reconciles account data; incomplete history remains a blocker; owned/unowned records are distinguished; instrumented transport proves zero submission/amend/close messages during shadow operation. Strategy decisions retain exact evidence and lag.

**S5 gate:** actual provider metadata and read-only flow satisfy the required contract. An SDK import test or synthetic metadata is not sufficient for this gate.

## S6 — autonomous demo execution

### F6.1 — Fenced order transport and send-time validation — TODO

**Depends on:** S4 gate, S5 gate. **Code:** `gateways/ctrader/orders.py`, `execution/dispatch.py`.

**Tasks:** sole gateway/account writer; authenticated core session/fencing; map supported command fields and broker IDs; refresh account/quote/deadline checks before send; explicit demo environment gate.

**Accept:** stale core session rejected; missing metadata or expiry prevents submission; actual order type/units match approved intent; order correlation IDs are not assumed to be broker idempotency guarantees. Live endpoints remain disabled.

### F6.2 — Fill/protection/cancellation lifecycle — TODO

**Depends on:** F6.1. **Code:** gateway execution events, `execution/protection.py`, `management.py`.

**Tasks:** partial fills, remaining quantity, attached stop/target confirmation, expiry, cancellation races, owned exits; verify broker protection/trigger sides; persist estimated versus actual risk and fill costs.

**Accept:** demo entry through exit reconciles with broker deals; all filled quantities have confirmed protection or invoke the documented recovery path; late fill after cancellation is handled; entry expiry never silently closes an established position. Test unsupported server expiry explicitly.

### F6.3 — Unknown outcomes and emergency recovery — TODO

**Depends on:** F6.2. **Code:** `execution/recovery.py`, reconciliation matching and supervisor hooks.

**Tasks:** recover from send timeout, missing acknowledgement, disconnect and process death; correlate broker history; protection repair/owned close policy; persistent uncertainty and halt state; handle unavailable connectivity truthfully.

**Accept:** accepted-but-unacknowledged command is found without duplicate submission; inconclusive matching remains halted; failed protection repair triggers policy; inability to close while disconnected is recorded rather than reported as successful. No unowned position mutation.

### F6.4 — Demo qualification suite and report — TODO

**Depends on:** F6.3. **Code:** `tests/broker/`, integration harness, evidence reports.

**Tasks:** run complete broker lifecycle plus deterministic transport fault suite; classify which scenarios occurred on actual demo versus simulated transport; compare actual stops, amounts, fees and events against expectations.

**Accept:** every acceptance scenario has evidence; zero duplicate submissions/unexplained exposure in the qualification suite; remaining limitations listed; account-specific capabilities recorded. Require explicit demo-test authorization/credentials before orders are placed, without treating this plan as deployment authorization.

**S6 gate:** verified autonomous demo trading with durable reconciliation. Demonstrating one successful market order is insufficient.

## S7 — operations, user controls and release readiness

### F7.1 — Status API and read-only dashboard — TODO

**Depends on:** F4.6; real-broker panels also depend on F5.4. **Code:** new `api/` and dashboard boundary, `observability/`.

**Tasks:** show mode/account alias, per-instance state, candidates/reasons, data age/lag, orders/protection, reserved risk, drawdown, halt reasons and version hashes; authenticated service API; loopback UI binding and event-to-evidence navigation.

**Accept:** UI restart has no trading effect; stale data clearly labelled; no broker secrets exposed; dashboard reads via API without mounting SQLite; every displayed fill is attributable to authoritative events.

### F7.2 — Explicit controls and alert deduplication — TODO

**Depends on:** F7.1, F4.4. **Code:** control API/CLI, `observability/alerts.py`.

**Tasks:** pause entries, resume after checks, flatten owned and halt; authenticated role checks, idempotent command IDs, audit log; deduplicated meaningful alerts; no automatic external messaging integrations.

**Accept:** pause differs from flatten; repeated controls do not duplicate close commands; resume cannot bypass unresolved state or loss limit; external trades untouched; secrets absent from notifications; alert recovery is distinguished from repeated failure.

### F7.3 — Production container and host deployment — TODO

**Depends on:** F6.4, F7.2. **Code:** Docker targets, demo/live Compose overrides, `deploy/` runbooks, CI.

**Tasks:** versioned immutable images; non-root/read-only services, resource/log limits, scoped networks/secrets, liveness/readiness distinction, signal handling/grace period, named volumes, CPU-architecture builds; explicit account/mode manifests.

**Accept:** clean Linux host deployment follows runbook; tests verify mount/port/role restrictions; unhealthy state inhibits trades without assuming Docker healthcheck restarts; Docker Desktop host sleep limitation documented; credentials never enter image layers. No second active writer during upgrades.

### F7.4 — Backup, restore, upgrade and soak drills — TODO

**Depends on:** F7.3. **Code:** persistence backup/export tooling, deployment/recovery runbooks, drill harness.

**Tasks:** consistent SQLite/evidence backup, protected token recovery, off-host copy, restore plus broker reconciliation, migration compatibility, graceful shutdown, version draining for open trades, measured resource/latency soak under representative load.

**Accept:** restore into isolated mode first; risk halts survive; cold restart reconciles unresolved commands; rollback plan handles schema differences; actual loss/recovery window and soak duration/results recorded. Set operational acceptance limits before the measured run, not after observing results.

**S7 gate:** controls, monitoring and recovery demonstrated on the intended host topology. Trading remains gated by S8 evidence and mandate.

## S8 — evaluation and controlled live release

### F8.1 — Reproducible performance evaluation — TODO

**Depends on:** F4.5, F5.3. **Code:** `simulation/evaluation.py`, report templates and versioned experiment manifests.

**Tasks:** untouched chronological evaluation, costs/latency/nonfill modeling, per-strategy/symbol/session and portfolio outcomes, uncertainty/drawdown/tail-loss analysis; record eligibility/exclusions and dependency/concentration effects.

**Accept:** preregister data period, minimum evidence and acceptance criteria before viewing results; no invented historical spreads or fills; parameter changes create new versions/evaluation periods; no profitable-strategy claim from detection tests. Insufficient evidence is a valid unresolved result.

### F8.2 — Deployment mandate and live pilot gate — TODO

**Depends on:** F8.1, S7 gate. **Code:** versioned release checklist/account policy and deployment manifest.

**Tasks:** record exact strategy/profile/image versions, supported account/broker, sizing/aggregate limits, monitoring/recovery and stop conditions; summarize open risks; obtain user's explicit live deployment instruction for the concrete release.

**Accept:** mandate matches runtime identity; risk controls demonstrated; no unresolved execution/data blocker; qualification evidence linked. Completion means gate satisfied, not “live trading has started.” Keep release and activation states separate.

### F8.3 — Pilot activation and post-activation review — TODO

**Depends on:** F8.2 and explicit activation instruction. **Code:** deployment record and operational reports.

**Tasks:** deploy exact approved release, verify startup reconciliation, observe initial outcomes, compare actual versus modeled execution, retain rollback/halt readiness; no automatic increase in scope or risk.

**Accept:** record activation time and release/account identity locally; summarize measured execution and any halt; discrepancies halt/review according to mandate. No promotion based solely on elapsed days or a profitable streak.

**S8 gate:** user-approved release and evidenced pilot review. A technically complete system can still remain unsuitable for live trading if strategy evidence is insufficient.

## S9 — optional model-backed strategy extension

### F9.1 — Model service and structured evaluator — DEFERRED

**Depends on:** S3 gate, F2.4. **Code:** future `model_service/`, strategy evaluator adapter and contracts.

**Tasks:** permissioned provider access, structured response validation, model/prompt/schema hashes, deadlines and cost budgets, input/output evidence capture, no credential access from workers.

**Accept:** malformed/late/unverifiable response produces no trade; replay uses recorded responses; fresh model reruns are not claimed deterministic; all proposals still pass account risk and ownership controls. Defer until a user-selected strategy actually needs this capability.

### F9.2 — Model-strategy evaluation and promotion — DEFERRED

**Depends on:** F9.1, F8.1. **Code:** evaluation fixtures/reports and package manifest.

**Tasks:** causal feature availability, prompt/version regression, adversarial input/structured-output tests, separate cost and latency evaluation; compare against declared baseline without changing account risk.

**Accept:** reproduce decisions from recorded model outputs, measure live-service variability, and qualify strategy independently. Adding a model does not bypass demo/live release gates.

## Decisions and external dependencies

| ID | Decision/input | Needed by | Current disposition |
|---|---|---|---|
| D01 | Python version, lock mechanism, dependency compatibility | F1.1 | Python 3.12 image is scaffold baseline; confirm SDK stack and record choice |
| D02 | Transport authentication and message framing limits | F2.4 | Authenticated internal TCP/JSON agreed; select concrete mechanism and bounds |
| D03 | TPR helper provenance and distributable fixtures | F3.1 | Available in original workspace, not in this repository; review/package explicitly |
| D04 | Provider app registration and authorized demo account | F5.1 | Not configured in this repo; request only when connection work requires it |
| D05 | Mandatory broker metadata availability | F5.2 | Unproven; missing fields must block execution, not be guessed |
| D06 | Exact execution/risk policy and thresholds | F4.2/F8.2 | Versioned examples for paper; concrete live mandate not yet selected |
| D07 | Production host and resources | F7.3 | Single always-on Linux Docker host proposed; host not selected |
| D08 | Performance/operational acceptance thresholds | F8.1/F7.4 | Must be fixed before evaluation/soak, not invented afterward |

For a consequential change, add `docs/decisions/NNNN-topic.md` with context, chosen option, alternatives, consequences and affected feature IDs; link it here. The plan does not authorize changing strategy parameters or deploying live trading by default.

## Delivery ledger

| Date | Feature/change | Reference | Evidence and limitations |
|---|---|---|---|
| 2026-10-15 | F0.1 scaffold | `578b26a` | Four local/container unit tests and Docker config/build/validation passed; pushed main; no trading runtime |
| 2026-10-15 | Detailed tracker and session instructions | This documentation change | Source baseline inspected; staged features/dependencies/gates and resumption workflow documented; no new runtime behavior |

For each later delivery, append rather than rewriting earlier evidence. If work is reverted or a completed feature regresses, reopen its status and record why.

## Handoff update template

Copy these fields into Current handoff when ending an implementation session:

```text
Date / owner:
Branch and latest implementation commit:
Feature IDs and statuses:
Delivered behavior and changed files:
Checks run, environment and actual results:
Known failures / missing inputs / decisions:
Uncommitted changes and why:
Broker/deployment state (if any):
Next eligible feature and exact first action:
Evidence / logs / PR references (no credentials):
```

Feature headings and the delivery ledger record completion; stage gates require integration evidence.

### Delivery F1.1

Status: DONE. Branch: `feature/toolchain_baseline`. Lock Python dependencies and verify Docker core and TLS gateway imports Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F1.1"`).

### Delivery F1.2

Status: DONE. Branch: `feature/value_event_contracts`. Validate immutable exact values and causal event snapshots; 11 container tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F1.2"`).

# Implementation tracker and session handoff

Last updated: 2026-10-15. Repository: `chukkilala007/autonomous-day-trading-sys`.

This is the go-to document for **what exists, what comes next, how to implement it, and how to resume after context is lost**. Feature status here is authoritative; architecture documents describe intended behavior, not delivered functionality. Update this file in the same change as the implementation it tracks.

## Current handoff — start here

| Item | Current value |
|---|---|
| Verified implementation baseline | S1–S4 feature commits on develop; locate F1.1–F4.6 with git log --all --grep |
| Completed stage | S1, S2, S3 and S4; persistent two-strategy paper runtime |
| Current implementation work | Implementing S5–S7; actual broker/host qualification remains separately gated |
| Next feature | integration-review |
| Next concrete action | Continue integration-review; preserve pending external acceptance gates |
| Next milestone | S5: verified provider data and read-only shadow runtime |
| Working branch policy | One feature/<feature_name> branch from develop; test, commit, merge --no-ff to develop |
| Trading state | Paper simulation only; two strategies, shared risk, protected entries/exits and reconciliation. No real broker orders or credentials |
| External inputs | F5.1 needs cTrader application/account authorization; TPR source is already ported with pinned provenance |
| Known limitations | Finite file-driven synthetic scenario, GBP linear-contract simulator, single-host topology. No real feed/gateway, UI, emergency account-wide flatten or production qualification |
| Verification evidence | 76 tests and 4 subtests passed in the installed Docker image; crash-during-evaluation replay matches clean decisions. Docker open-exposure restart drill recorded below. GitHub CI not yet inspected |
| Uncommitted implementation | None intended after the F4.6 commit; always inspect git status when resuming |

Future handoffs must name the active feature, changes already made, exact failing/passing checks, unresolved decisions, and the next action. Never leave “continue implementation” as the only next step.

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
docker compose up --build -d
docker compose exec core trading-platform status --state /state/core.db
docker compose --profile tools run --rm tests
python3 scripts/paper_smoke.py
```

The default stack runs the two-strategy synthetic paper scenario and remains waiting for input. The tools-profile `validate` service checks an instance mandate; `tests` runs the full suite. Future S5–S8 commands remain proposed until implemented.

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
| S1 | Contracts, configuration, registry and reproducible toolchain | DONE | Valid/invalid package and proposal fixtures behave consistently inside Docker |
| S2 | Durable event processing and isolated workers | DONE | Crash/replay preserves state without cross-instance contamination |
| S3 | Strategy adapters and causal replay | DONE | TPR parity plus unrelated fixture proves strategy independence |
| S4 | Portfolio risk and autonomous paper lifecycle | DONE | Two strategies share risk and recover safely from simulated failures |
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

### F1.3 — Decision, proposal and management contracts — DONE

**Depends on:** F1.2. **Code:** `contracts/decisions.py`, `orders.py`, `capabilities.py`.

**Tasks:** discriminated NO_ACTION/WATCH/ENTRY/MANAGEMENT/UNAVAILABLE envelopes; separate market/limit/stop proposal schemas; ownership, expiry, preconditions and state revisions; generic protection/exit specification; namespaced strategy diagnostics and stable action IDs.

**Accept:** market entry without TP1 is representable under an appropriate profile; incomplete executable proposals fail; one strategy cannot name an unowned management target; do not impose 2R or TPR states globally. Cover stale deadlines and invalid amendment revisions.

### F1.4 — Configuration and deployment mandate validation — DONE

**Depends on:** F1.3. **Code:** `contracts/config.py`, `config/`, `cli.py`.

**Tasks:** versioned instance, account-policy, risk/execution profile schemas; paper/shadow/demo/live mode semantics; explicit account aliases and immutable config hash; secret references without secret values; replace or clearly deprecate scaffold `validate-config` with `validate-instance`.

**Accept:** unknown/contradictory fields rejected; demo/live require matching configured environment and account binding; shadow has no submission capability; per-strategy budgets cannot exceed account policy. Tests must not require real credentials.

### F1.5 — Registry and plugin protocol — DONE

**Depends on:** F1.4. **Code:** `registry/loader.py`, `manifest.py`, `contracts/strategy.py`.

**Tasks:** reviewed package allowlist, digest/version checks, manifest requirements and capabilities, initialize/evaluate/validate/migrate hooks; distinguish package from instance; instance state namespace; dependency compatibility checks.

**Accept:** two fixture packages load through configuration without core edits; malformed manifest, digest mismatch, duplicate instance and unsupported capability fail with actionable reasons; common modules cannot import concrete strategy packages. Add an architecture dependency check to CI.

**S1 gate:** F1.1–F1.5 DONE; versioned input and decision fixtures pass through package loading and validation inside the container. No broker commands exist yet.

## S2 — durable runtime and worker isolation

### F2.1 — Database schema and migration boundary — DONE

**Depends on:** F1.3. **Code:** `persistence/database.py`, `migrations/`, `repositories.py`.

**Tasks:** schema-version tracking; tables for events/cursors, snapshots, instance states, decisions/intents, reservations, commands/attempts, broker entities, account checkpoints and halts; unique constraints; WAL configuration and one-writer enforcement; local named-volume ownership.

**Accept:** migrations work on empty and prior-version fixtures; conflicting writer startup fails; restart retains state; rollback after an injected transaction failure leaves no half-written decision. Backups use SQLite APIs, not a live-file copy.

### F2.2 — Event journal and atomic evaluation commits — DONE

**Depends on:** F2.1, F1.5. **Code:** `runtime/journal.py`, `persistence/events.py`, `snapshots.py`.

**Tasks:** journal accepted inputs; commit consumed cursor, next state and decisions together; immutable evidence storage/reference/hash; revision records; idempotent event ingestion; distinguish processing order from market source time.

**Accept:** crash before/after commit yields either old or complete new state; duplicate delivery cannot duplicate decisions; evidence hash mismatch blocks use; replay cursor never skips unprocessed events. Retain earlier evidence when provider revisions arrive.

### F2.3 — Causal scheduler and virtual clock — DONE

**Depends on:** F2.2. **Code:** `runtime/scheduler.py`, `clock.py`, `simulation/clock.py`.

**Tasks:** bar/tick/timer/execution subscriptions; bounded per-instance queues; explicit deadline/watermark policies; multi-instrument as-of views; virtual time for replay; backpressure and gap signals.

**Accept:** no future bar or unpublished feature reaches an evaluation; deterministic event ordering; queue overflow blocks rather than silently loses required data; stopped/closed sessions do not fabricate bars. One blocked instance does not starve unrelated instances.

### F2.4 — Authenticated container worker transport — DONE

**Depends on:** F2.3. **Code:** `runtime/worker.py`, `transport.py`, Docker targets and Compose networks.

**Tasks:** bounded length-framed JSON, role/instance authentication, handshake schema versions, request IDs, timeouts and heartbeats; one worker container per instance; core supplies state and read-only snapshots; no strategy database/secret mounts.

**Accept:** oversized/malformed/unauthenticated messages rejected; stale response cannot update current state; worker timeout/crash inhibits its entries; worker cannot directly reach broker control; denied-network and secret-mount checks pass. Do not claim arbitrary hostile Python is fully sandboxed.

### F2.5 — Recovery state and instance replacement — DONE

**Depends on:** F2.4. **Code:** `runtime/recovery.py`, `registry/lifecycle.py`.

**Tasks:** BOOTING/WARMING/READY/DEGRADED/HALTED lifecycle; persistent halt reasons; initialization/replay on restart; explicit state migrations; drain-and-replace behavior that retains old version ownership for unresolved orders/positions.

**Accept:** restart does not clear a halt; unavailable state migration fails explicitly; duplicate instance registration rejected; replacement cannot adopt another version's exposure silently. Use synthetic owned-position fixtures until real execution exists.

**S2 gate — passed:** `test_core_and_worker_killed_during_evaluation_replay_identically` kills actual core/worker subprocesses mid-RPC inside the test container, then verifies replay produces identical committed state and decisions to a clean run. `test_worker_failure_preserves_state_and_sibling_progress` verifies the failed instance cannot commit while its sibling progresses. The Docker restart drill additionally restarts both independent worker containers with owned exposure.

## S3 — strategy adapters and causal replay

### F3.1 — TPR baseline provenance and portability — DONE

**Depends on:** F1.5. **Code:** `strategies/tpr1/`, `tests/fixtures/tpr1/`, provenance manifest.

**Tasks:** obtain reviewed existing helper and reference rules from the original workspace; record source/version/hashes and licensing suitability; package only required code and sanitized synthetic fixtures; identify strategy-specific versus generic validation. No personal paths or account snapshots in runtime imports.

**Accept:** baseline imports in a clean container; provenance identifies exact source; fixtures contain no secrets/account identifiers; old monitor state is never migrated into execution state. If source is unavailable, mark this feature BLOCKED while the unrelated fixture proceeds.

### F3.2 — TPR strategy adapter and parity suite — DONE

**Depends on:** F3.1, F2.3. **Code:** `strategies/tpr1/adapter.py`, `manifest.*`, `tests/replay/test_tpr_parity.py`.

**Tasks:** wrap helper into generic protocol; package M1/M5/context requirements and parameters; map candidate events into common decisions; keep TPR-specific geometry/cost rules in its validator/profile; separate research touches from confirmed execution events.

**Accept:** original baseline and adapter agree on candidate IDs, anchors, timing, reasons and geometry; causal pivots, target retirement, missing context and pending expiry tests pass; future bars do not alter earlier decisions. No unexplained parity differences accepted.

### F3.3 — Independent timer/H1 fixture strategy — DONE

**Depends on:** F1.5, F2.3. **Code:** `strategies/timer_fixture/`, fixture configuration/tests.

**Tasks:** deterministic synthetic strategy using H1/timer events, a market-entry proposal, protective stop and timed exit; explicitly label it an architecture fixture, not a production strategy.

**Accept:** no M1/TP1/2R requirement; package loads without touching core; separate instance state; management proposals use owned broker-view fixtures. Tests fail if TPR assumptions leak into shared code.

### F3.4 — Replay CLI and evidence reports — DONE

**Depends on:** F3.2, F3.3, F2.5. **Code:** `simulation/replay.py`, `market_data/history.py`, `cli.py`.

**Tasks:** normalized recorded-data loader, duplicates/gaps/revisions policy, causal clock, immutable run/config manifest, decision/reason summaries and reproducibility comparison. Replay mode is isolated from runtime volumes and broker endpoints.

**Accept:** both strategies replay using identical infrastructure; deterministic rerun matches; conflicting history revisions fail visibly; source quotes are not backdated; missing execution data prevents fabricated P&L. CLI exit codes distinguish valid no-signal output from unavailable input.

**S3 gate:** run both strategies in Docker using configuration-only selection and compare replay output; TPR parity and unrelated fixture pass. This proves architecture compatibility, not market edge.

## S4 — shared risk and autonomous paper trading

### F4.1 — Portfolio ownership and account arbitration — DONE

**Depends on:** F2.1, F1.4. **Code:** `portfolio/ownership.py`, `allocation.py`, `arbiter.py`.

**Tasks:** account/instance attribution, shared pending/open exposure view, exclusive-symbol initial policy, configured priority/time/ID ordering, concentration buckets and external-exposure handling.

**Accept:** simultaneous conflicting intents have deterministic outcomes; one strategy cannot cancel another's trade; unknown external exposure blocks entries; opposite signals are not silently netted; budgets are subdivisions of the account ceiling.

### F4.2 — Risk model interface and stop-based sizing — DONE

**Depends on:** F4.1. **Code:** `risk/models.py`, `sizing.py`, `valuation.py`.

**Tasks:** independently verified unit loss/currency conversion; costs/slippage allowance; minimum/maximum/step rounding down; margin check; risk-profile selection; conservative worst-fill valuation.

**Accept:** Decimal fixtures cover GBP/USD conversion, non-unit volume steps and minimum size over budget; unknown costs/valuation reject; stop never moves to force size; unsupported nonlinear contracts fail instead of using the linear model.

### F4.3 — Atomic reservations and persistent circuit breakers — DONE

**Depends on:** F4.2, F2.2. **Code:** `risk/reservations.py`, `limits.py`.

**Tasks:** serialized budget checks/reservation; pending/partial-fill/in-flight exposure; cash-flow-adjusted equity checkpoints; daily timezone boundary, loss streak and cooldown; distinguish entry blocking from risk-reducing actions.

**Accept:** concurrent attempts cannot oversubscribe; unknown submissions keep reservations; confirmed terminal events release once; restarts/DST/deposits cannot reset or distort limits; close/reduce actions remain possible when entry budget is exhausted.

### F4.4 — Order planner, lifecycle and durable outbox — DONE

**Depends on:** F4.3. **Code:** `execution/planner.py`, `state_machine.py`, `outbox.py`.

**Tasks:** map supported profiles into generic commands; pre-send price/deadline/revision checks; create reservation/outbox atomically; submission attempt journal; ACCEPTED/PART_FILLED/FILLED/CANCEL_PENDING/UNKNOWN/terminal transitions; ownership-based management.

**Accept:** unsupported order semantics fail; duplicate/out-of-order acknowledgements do not regress state; timeout after send creates UNKNOWN, not an automatic retry; no blind release on cancel request; a stale amendment cannot overwrite a fill.

### F4.5 — Paper broker and fault scenarios — DONE

**Depends on:** F4.4, F3.4. **Code:** `simulation/broker.py`, `fills.py`, `faults.py`.

**Tasks:** execution-port implementation driven by contemporaneous bid/ask/ticks; spread/commission/slippage assumptions; stop-limit nonfills/expiry; partial fills; rejection/disconnect/timeout injection; conservative ambiguity outcomes.

**Accept:** no fill at an unavailable price; entry touch alone does not prove a fill; full event lifecycle matches broker contract fixtures; configurable faults reproduce cancel/fill race and accepted-but-unacknowledged submission without duplicates. Unknown costs remain unknown.

### F4.6 — Integrated persistent paper stack — DONE

**Depends on:** F4.5, F2.5. **Code:** Compose services, CLI run/status commands, `tests/execution/` end-to-end suite.

**Tasks:** connect input → workers → risk → executor → paper broker → state; named volumes and status summaries; continuously process owned execution events; simulator replaces real gateway in default mode.

**Accept:** documented single Compose command runs two configured instances; trades and reasons trace to evidence; core/worker/simulator restarts preserve limits and ownership; repeat the fault matrix and show no unexplained exposure. Default stack contains no real broker credentials or reachable order endpoint.

**S4 gate — passed:** both strategies complete protected paper entry/exit and release all reservations; process crash/replay and independent-container restart preserve order IDs, ownership and state. See F4.6 delivery evidence below. This milestone is entirely simulated.

## S5 — broker feasibility and read-only shadow operation

### F5.1 — cTrader authentication and account binding — IN_PROGRESS

**Depends on:** F1.1, F1.4. **Code:** `gateways/ctrader/client.py`, `auth.py`, gateway image/secret configuration.

**Tasks:** SDK/Twisted process; TLS, heartbeat and reconnect; application/account authentication; mounted secret input and atomic refreshed-token persistence; rate-limited retry/backoff; explicit environment/account identity checks.

**Accept:** demo connection established with authorized credentials; mismatched account fails; logs redact secrets; restart/token-refresh tests preserve credentials safely; execution capability remains disabled. Use fake transport tests when real authorization is unavailable and label live integration unverified.

### F5.2 — Provider capability audit and normalization — IN_PROGRESS

**Depends on:** F5.1, F1.2. **Code:** `gateways/ctrader/metadata.py`, `normalization.py`; provider-evidence report.

**Tasks:** verify protocol price/volume scaling, exact symbols, timestamp semantics, tick grid, candle basis, real session status, contract value, fees, conversion, margin and protection/order capabilities; record provenance and missing fields explicitly.

**Accept:** documented field-by-field evidence and conversion fixtures; no digits-as-tick or schedule-as-live-state inference; unsatisfied mandatory capability blocks execution. If broker-native extension is necessary, create a scoped feature/decision record rather than loosening validation.

### F5.3 — Streaming feed, history and gap repair — IN_PROGRESS

**Depends on:** F5.2, F2.3. **Code:** `market_data/service.py`, `bars.py`, `coverage.py`; gateway subscriptions.

**Tasks:** per-manifest subscriptions/warm-up, shared compatible feeds, finalized bar validation, incremental history overlap, rate limiting, revision audit and reconnect backfill; session-aware missing-interval detection.

**Accept:** no unfinished bars in closed-bar events; missing intervals inhibit relevant decisions; unchanged subscription quote cannot prove an open market; backfill does not resurrect an expired opportunity; multi-instrument snapshots use verified causal coverage.

### F5.4 — Read-only account reconciliation and shadow stack — IN_PROGRESS

**Depends on:** F5.3, F4.6. **Code:** `execution/reconciliation.py`, shadow configuration and Compose override.

**Tasks:** ingest balances, pending orders, positions and deals without mutations; account health/exposure view; real-feed decisions and paper projections in separately labelled storage; assert no order-write path in shadow mode.

**Accept:** cold start reconciles account data; incomplete history remains a blocker; owned/unowned records are distinguished; instrumented transport proves zero submission/amend/close messages during shadow operation. Strategy decisions retain exact evidence and lag.

**S5 gate:** actual provider metadata and read-only flow satisfy the required contract. An SDK import test or synthetic metadata is not sufficient for this gate.

## S6 — autonomous demo execution

### F6.1 — Fenced order transport and send-time validation — IN_PROGRESS

**Depends on:** S4 gate, S5 gate. **Code:** `gateways/ctrader/orders.py`, `execution/dispatch.py`.

**Tasks:** sole gateway/account writer; authenticated core session/fencing; map supported command fields and broker IDs; refresh account/quote/deadline checks before send; explicit demo environment gate.

**Accept:** stale core session rejected; missing metadata or expiry prevents submission; actual order type/units match approved intent; order correlation IDs are not assumed to be broker idempotency guarantees. Live endpoints remain disabled.

### F6.2 — Fill/protection/cancellation lifecycle — IN_PROGRESS

**Depends on:** F6.1. **Code:** gateway execution events, `execution/protection.py`, `management.py`.

**Tasks:** partial fills, remaining quantity, attached stop/target confirmation, expiry, cancellation races, owned exits; verify broker protection/trigger sides; persist estimated versus actual risk and fill costs.

**Accept:** demo entry through exit reconciles with broker deals; all filled quantities have confirmed protection or invoke the documented recovery path; late fill after cancellation is handled; entry expiry never silently closes an established position. Test unsupported server expiry explicitly.

### F6.3 — Unknown outcomes and emergency recovery — IN_PROGRESS

**Depends on:** F6.2. **Code:** `execution/recovery.py`, reconciliation matching and supervisor hooks.

**Tasks:** recover from send timeout, missing acknowledgement, disconnect and process death; correlate broker history; protection repair/owned close policy; persistent uncertainty and halt state; handle unavailable connectivity truthfully.

**Accept:** accepted-but-unacknowledged command is found without duplicate submission; inconclusive matching remains halted; failed protection repair triggers policy; inability to close while disconnected is recorded rather than reported as successful. No unowned position mutation.

### F6.4 — Demo qualification suite and report — BLOCKED

**Depends on:** F6.3. **Code:** `tests/broker/`, integration harness, evidence reports.

**Tasks:** run complete broker lifecycle plus deterministic transport fault suite; classify which scenarios occurred on actual demo versus simulated transport; compare actual stops, amounts, fees and events against expectations.

**Accept:** every acceptance scenario has evidence; zero duplicate submissions/unexplained exposure in the qualification suite; remaining limitations listed; account-specific capabilities recorded. Require explicit demo-test authorization/credentials before orders are placed, without treating this plan as deployment authorization.

**S6 gate:** verified autonomous demo trading with durable reconciliation. Demonstrating one successful market order is insufficient.

## S7 — operations, user controls and release readiness

### F7.1 — Status API and read-only dashboard — IN_PROGRESS

**Depends on:** F4.6; real-broker panels also depend on F5.4. **Code:** new `api/` and dashboard boundary, `observability/`.

**Tasks:** show mode/account alias, per-instance state, candidates/reasons, data age/lag, orders/protection, reserved risk, drawdown, halt reasons and version hashes; authenticated service API; loopback UI binding and event-to-evidence navigation.

**Accept:** UI restart has no trading effect; stale data clearly labelled; no broker secrets exposed; dashboard reads via API without mounting SQLite; every displayed fill is attributable to authoritative events.

### F7.2 — Explicit controls and alert deduplication — DONE

**Depends on:** F7.1, F4.4. **Code:** control API/CLI, `observability/alerts.py`.

**Tasks:** pause entries, resume after checks, flatten owned and halt; authenticated role checks, idempotent command IDs, audit log; deduplicated meaningful alerts; no automatic external messaging integrations.

**Accept:** pause differs from flatten; repeated controls do not duplicate close commands; resume cannot bypass unresolved state or loss limit; external trades untouched; secrets absent from notifications; alert recovery is distinguished from repeated failure.

### F7.3 — Production container and host deployment — IN_PROGRESS

**Depends on:** F6.4, F7.2. **Code:** Docker targets, demo/live Compose overrides, `deploy/` runbooks, CI.

**Tasks:** versioned immutable images; non-root/read-only services, resource/log limits, scoped networks/secrets, liveness/readiness distinction, signal handling/grace period, named volumes, CPU-architecture builds; explicit account/mode manifests.

**Accept:** clean Linux host deployment follows runbook; tests verify mount/port/role restrictions; unhealthy state inhibits trades without assuming Docker healthcheck restarts; Docker Desktop host sleep limitation documented; credentials never enter image layers. No second active writer during upgrades.

### F7.4 — Backup, restore, upgrade and soak drills — IN_PROGRESS

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

### Delivery F1.3

Status: DONE. Branch: `feature/decision_contracts`. Add strategy-neutral entry and owned management decisions; 13 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F1.3"`).

### Delivery F1.4

Status: DONE. Branch: `feature/deployment_configuration`. Validate deployment mandates and shadow no-submission semantics; 15 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F1.4"`).

### Delivery F1.5

Status: DONE. Branch: `feature/strategy_registry`. Load reviewed digest-bound plugins and enforce dependency boundaries; S1 gate 17 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F1.5"`).

### Delivery F2.1

Status: DONE. Branch: `feature/durable_database`. Add single-writer SQLite migrations rollback and consistent backups; 19 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F2.1"`).

### Delivery F2.2

Status: DONE. Branch: `feature/event_journal`. Commit event cursors state and decisions atomically with evidence hashes; 20 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F2.2"`).

### Delivery F2.3

Status: DONE. Branch: `feature/causal_scheduler`. Bound per-instance queues and enforce causal clock and snapshot cutoffs; 22 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F2.3"`).

### Delivery F2.4

Status: DONE. Branch: `feature/worker_transport`. Authenticate bounded worker RPC and verify Docker network and secret isolation; 24 tests plus container smoke pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F2.4"`).

### Delivery F2.5

Status: DONE. Branch: `feature/instance_recovery`. Persist halts and retain old strategy ownership during replacement; 25 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F2.5"`).

### Delivery F3.1

Status: DONE. Branch: `feature/tpr_baseline`. Package provenance-pinned TPR helper and original synthetic tests; 54 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F3.1"`).

### Delivery F3.2

Status: DONE. Branch: `feature/tpr_strategy_adapter`. Adapt TPR with baseline parity and explicit paper bid-ask conversion; 56 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F3.2"`).

### Delivery F3.3

Status: DONE. Branch: `feature/timer_strategy`. Add independent timer strategy with protected market entry and timed exit; 57 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F3.3"`).

### Delivery F3.4

Status: DONE. Branch: `feature/causal_replay`. Replay both reviewed strategies with causal history and immutable reports; 59 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F3.4"`).

### Delivery F4.1

Status: DONE. Branch: `feature/portfolio_ownership`. Enforce owned positions exclusive symbols and deterministic arbitration; 61 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F4.1"`).

### Delivery F4.2

Status: DONE. Branch: `feature/risk_sizing`. Size linear contracts with verified costs conversion and round-down grids; 63 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F4.2"`).

### Delivery F4.3

Status: DONE. Branch: `feature/risk_reservations`. Reserve account risk atomically and persist cashflow-adjusted loss limits; 64 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F4.3"`).

### Delivery F4.4

Status: DONE. Branch: `feature/order_lifecycle`. Persist order attempts and reconcile partial or unknown outcomes without blind retries; 66 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F4.4"`).

### Delivery F4.5

Status: DONE. Branch: `feature/paper_broker`. Simulate durable bid-ask fills expiry partial cancellations and lost acknowledgements; 70 tests pass Tests passed before this commit. Commit reference: this feature commit (locate with `git log --all --grep="F4.5"`).

### Delivery F4.6

Status: DONE. Branch: `feature/integrated_paper_stack`. Commit reference: this feature commit (`git log --all --grep="F4.6"`).

Delivered authenticated core → two strategy workers → shared risk/outbox → independent persistent simulator orchestration; `run-paper` and read-only persisted `status`; named volumes, private networks, non-root/read-only containers and an isolated automated restart drill. Added failure checks for worker isolation, core/worker death mid-evaluation and unknown broker acknowledgements. Fixed exact high-precision Decimal hashing, validation of worker state/output, pre-import package digest checks and concentration accounting. Unknown sends block subsequent entry dispatch; a partial order must cancel its unfilled remainder before reduction.

Verification on 2026-10-15:

- `docker compose build core`: passed with pinned Python image and hashed dependencies.
- `docker compose -p s4-final-tests --profile tools run --rm tests`: **76 passed, 4 subtests passed** in the installed image.
- `python3 scripts/paper_smoke.py`: **PASS**. Unique project started with two orders and two active risk reservations; core received SIGKILL while exposure was open; both worker containers and simulator restarted; recovered core completed the same two order IDs. Final state: both cursors 4, both READY, two CLOSED orders, zero positions, zero reservations and zero rejections. The script removed only its own generated test volumes.
- Earlier completed-scenario restart also preserved both closed orders without duplicate submissions; WARMING after restart without new input is expected.
- CI definition now runs build, configuration validation, the container suite and the isolated restart drill. These are observed local results; GitHub-hosted CI has not been claimed as passed.

Current limits and scope: synthetic file input and GBP linear-contract paper economics; no real broker gateway/feed or profitability evidence. Daily breakers inhibit entries and permit risk reduction; account-wide emergency flatten/operator controls remain future work. Paper protections/timed exits require subsequent ticks. Halted workers remain halted across restarts until explicit recovery; operational resume/repair is not a user-facing S4 control. Single-host trusted-package deployment; production backup, retention, soak and cross-platform qualification remain later gates. See `docs/container-deployment.md` for details.

All 20 requested implementation features F1.1–F4.6 are DONE (plus existing F0.1 scaffold). Each has a feature branch from develop and a tested merge. Next eligible feature is F5.1; do not activate real broker trading as part of this completed S4 scope.

### Delivery F5.1 — implementation slice

Branch: `feature/ctrader_authentication`. Status: IN_PROGRESS. Implemented verified-TLS demo binding, bounded SDK reconnect, read-only allowlist and atomic private token rotation. Initial gateway suite: 79 passed, 1 TLS-test inspection failure, 4 subtests passed; correction and rerun recorded in the follow-up delivery. Actual authorized connection pending credentials; F5.1 remains IN_PROGRESS. Feature commit: `git log --all --grep="F5.1:"`.

### Delivery F5.1 — implementation slice

Branch: `feature/ctrader_authentication_checks`. Status: IN_PROGRESS. Corrected TLS endpoint test for the pinned Twisted implementation; gateway suite now verified: 80 passed and 4 subtests passed. Actual authentication pending mounted credentials. Feature commit: `git log --all --grep="F5.1:"`.

### Delivery F5.2 — implementation slice

Branch: `feature/provider_normalization`. Status: IN_PROGRESS. Added exact protocol price/volume/time conversion and expiring capability evidence; unknown or synthetic metadata cannot enable orders. 83 gateway tests and 4 subtests pass. Actual broker verification pending. Feature commit: `git log --all --grep="F5.2:"`.

### Delivery F5.3 — implementation slice

Branch: `feature/market_data_coverage`. Status: IN_PROGRESS. Implemented durable causal feed cache, verified-session gap handling, SDK subscription/history bridge and reconnect coverage gating. 86 tests and 4 subtests pass. Streaming provider qualification and paginated deep history remain pending; incomplete history blocks decisions. Feature commit: `git log --all --grep="F5.3:"`.

### Delivery F5.4 — implementation slice

Branch: `feature/readonly_shadow`. Status: IN_PROGRESS. Added demo read-only collector, account identity/ownership reconciliation, no-executor shadow evaluation path and separate credential-scoped Compose deployment. 88 tests and 4 subtests pass. Actual provider flow and full shadow deployment qualification pending. Feature commit: `git log --all --grep="F5.4:"`.

### Delivery F6.1 — implementation slice

Branch: `feature/fenced_demo_transport`. Status: IN_PROGRESS. Implemented persistent core fencing, demo-only opt-in, fresh account/quote and capability checks, exact volume mapping and write-ahead uncertainty with no blind resend. 90 tests and 4 subtests pass. Tested with fake transport; S5 provider gate prevents actual demo activation. Feature commit: `git log --all --grep="F6.1:"`.

### Delivery F6.2 — implementation slice

Branch: `feature/broker_execution_lifecycle`. Status: IN_PROGRESS. Added durable broker-event ledger, partial-fill ownership, revision checks, protection halts and owned close/reduce/protect request mapping. 92 tests and 4 subtests pass. Actual demo entry-to-exit, trigger sides, cancellation and cost qualification remain pending. Feature commit: `git log --all --grep="F6.2:"`.

### Delivery F6.3 — implementation slice

Branch: `feature/demo_uncertainty_recovery`. Status: IN_PROGRESS. Added conservative unique history matching, durable unresolved halts and explicit protection-repair/owned-close policy outcomes. 93 tests and 4 subtests pass. Disconnection never reports successful closure; actual demo recovery remains unqualified. Feature commit: `git log --all --grep="F6.3:"`.

### Delivery F6.4 — implementation slice

Branch: `feature/demo_qualification`. Status: BLOCKED. Added immutable qualification reporting that distinguishes actual demo evidence from deterministic faults and refuses incomplete qualification. 94 tests and 4 subtests pass. Actual demo suite BLOCKED on credentials and explicit order-test authorization. Feature commit: `git log --all --grep="F6.4:"`.

### Delivery F7.1 — implementation slice

Branch: `feature/status_dashboard`. Status: IN_PROGRESS. Added authenticated status/evidence API, separate no-database dashboard and loopback UI profile. 95 tests and 4 subtests pass; installed API verified two closed orders and stale-data label. Browser visual acceptance pending: both available browser runtimes failed to attach. Feature commit: `git log --all --grep="F7.1:"`.

### Delivery F7.2 — implementation slice

Branch: `feature/operator_controls`. Status: DONE. Implemented authenticated idempotent control API/CLI, immediate entry pause, checked resume, owned paper flatten-and-halt and persistent transition alerts. 97 tests and 4 subtests pass. Actual demo integration remains gated; stale/disconnected flatten stays pending. Feature commit: `git log --all --grep="F7.2:"`.

### Delivery F7.3 — implementation slice

Branch: `feature/hardened_deployment`. Status: IN_PROGRESS. Separated slim runtime and gateway/test targets, added log/resource and mount/network audits, immutable-image overrides, readiness and host runbook plus native architecture CI. Installed tests: 93 passed with 4 SDK skips; gateway 98 passed; 4 subtests each. Docker restart drill and isolation audit pass. Remote clean-host and architecture CI qualification pending. Feature commit: `git log --all --grep="F7.3:"`.

### Delivery F7.4 — implementation slice

Branch: `feature/backup_restore_soak`. Status: IN_PROGRESS. Implemented dual-writer-lock quiesced archives, checksum/schema verification and isolated halted restore. 100 tests and 4 subtests pass; 300-event 60-second soak p95 29ms RSS39MiB; restore 28ms with zero committed-event loss and preserved exposure/halt. Off-host secret backup and intended-host qualification pending. Feature commit: `git log --all --grep="F7.4:"`.

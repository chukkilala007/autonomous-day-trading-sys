# Implementation tracker and session handoff

Last updated: 2026-10-21. Repository: `chukkilala007/autonomous-day-trading-sys`.

This is the go-to document for **what exists, what comes next, how to implement it, and how to resume after context is lost**. Feature status here is authoritative; architecture documents describe intended behavior, not delivered functionality. Update this file in the same change as the implementation it tracks.

## Current handoff — start here

| Item | Current value |
|---|---|
| Verified baseline | S1–S4 complete; S5–S7 partial; S8 unstarted |
| Latest features | Opt-in bounded quote buffering for the read-only gateway; strict release validation and pending-snapshot inhibition |
| Account state | Demo account authenticated; no orders enabled or sent; private rotated tokens preserved |
| Actual qualification | Fresh probes 024/026 renewed bid basis; probe 026 certified the Oct20 XAUUSD daily closure; probe 025 confirmed an unexplained EURUSD empty minute |
| Actual shadow result | XAUUSD run-022 bounded buffer PASS: 601.8s, 1,475 spots, 1,288 buffered/released, zero quote rejections, reconnect PASS, 880 decisions, zero orders |
| Current blocker | EURUSD run-021 M1 gap ending Oct20 23:44UTC; no closure inferred. XAUUSD bounded pass does not close sustained availability, capability or execution acceptance |
| Next concrete action | Collect fresh EURUSD evidence when its required history is complete (next probe 027, shadow 023), then repeat separate 600s acceptance. Continue broker capability qualification before bounded-order approval |
| Capability blockers | Broker economics/order/protection qualification and bounded demo approval remain; buffering does not enable execution |
| Working branch policy | One feature/<feature_name> from develop; test, commit, merge --no-ff; publish tested changes |
| Latest tests | Installed gateway: 290 passed + 4 subtests (6.74s), including causal queue bounds, clock jumps, stale callbacks and restart tests |
| External inputs | This Mac/Docker Desktop is demo host; separate Linux/registry not required. Off-host backup destination unspecified. Actual orders require explicit bounded authorization |
| Publication | Buffer implementation merged at 8e3472d; CI 39480736712 SUCCESS. Fresh evidence commit 0bd2899 and develop merge 6bc47b3 pushed successfully; this handoff update is documentation only |

Publication history: earlier implementation commits remain merged. Current acceptance changes are documentation/evidence only and do not enable broker orders.


Future handoffs must name the active feature, changes already made, exact failing/passing checks, unresolved decisions, and the next action. Never leave “continue implementation” as the only next step.

## Remaining work and acceptance boundaries (2026-10-16)

| Feature | Implemented and tested locally | Required before parent can be DONE |
|---|---|---|
| F5.1 | Verified TLS, demo binding, rotated private tokens, terminal refresh failure | DONE: actual auth, token rotation and forced reconnect/re-auth observed; no order permission |
| F5.2 | Exact unit normalization, expiring account-bound evidence, hedged-account gate | Broker-specific tick/basis/session/fees/conversion/margin/protection and account-type audit |
| F5.3 | Durable causal feed, gap/revision checks, bounded history pagination | Actual full history and forced reconnect observed; sustained quote validity remains unqualified |
| F5.4 | Separate gateway/core/workers, authenticated read-only snapshot RPC, zero order path | Bounded both-strategy full-history run passed; sustained feed availability and remaining account capability gates stay open |
| F6.1–F6.3 | Fencing, uncertain-send persistence, order/position ledger, owned cancel/close/protect, recovery supervisor | Offline core/outbox adapter, TCP controller, service loop and settlement-gated reconciliation implemented. Strict valuation input exporter and disabled lifecycle assembly now delivered (F5.2a/F6.3b/c). Raw broker economics/history mapping, authorized activation and broker acceptance still required |
| F6.4 | Fail-closed qualification report and deterministic faults | Explicit demo-test authorization plus actual lifecycle, cancellation-race, protection and reconnect evidence |
| F7.1 | Authenticated API, dashboard proxy, stale labels, evidence links | Actual read-only Chrome broker panel and decision evidence passed; order execution acceptance remains under F6 |
| F7.2 | Tested paper pause/resume/owned flatten, deduplicated local alerts | DONE for delivered paper controls; demo wiring belongs to pending F6 service integration |
| F7.3 | Slim Docker targets, isolation audit, resource/log limits, immutable release helper, native-architecture CI | Prior develop CI observed passing on native AMD64/ARM64; immutable publication and clean intended-host qualification remain outside offline scope |
| F7.4 | Quiesced paired paper archive, isolated halted restore, measured local soak/recovery | Encrypted secret recovery tooling tested offline; actual off-host/key recovery, intended-host soak and real-account restore reconciliation remain outside offline scope |

The user explicitly selected **implement and test offline; leave actual broker orders disabled** on 2026-10-16. Offline adapter/service work is now delivered, superseding the earlier dependency deferral. It does not supply or infer actual broker economics. `DemoAPI` requires fresh account-bound valuation evidence and explicit settlement evidence; missing facts block entries or keep reservations unresolved. A provider-specific exporter and authorized gateway activation are future qualification work, not a configuration switch justified by synthetic tests. Netted accounts remain unsupported.

Offline subfeatures delivered under that mandate:

- **F5.3a DONE:** generation-scoped subscriptions, incremental revision overlap, full reconnect repair and incomplete-history cursor checks.
- **F6.1a DONE:** bound demo RPC adapter, shared risk/outbox runtime and deterministic protobuf accept/fill/close integration.
- **F6.2a DONE:** owned event projection, correlation-collision rejection, settlement-gated closure, broker-confirmed management and stale-request guards.
- **F6.3a DONE:** core service cycle, authenticated TCP boundary, reactor dispatch factory and recovery-supervisor calls, exercised offline. No real-order launcher enabled.
- **F7.4a DONE:** encrypted secret archive/restore with synthetic-secret tamper, wrong-key, private-file and overwrite-refusal tests.

Parent stages remain open because their original acceptance gates include actual broker/host evidence. Chrome visual acceptance passed on 2026-10-17 for paper and synthetic shadow fixtures; the in-app browser native dependency failure persists. Actual read-only broker-panel acceptance passed with fresh XAUUSD data on 2026-10-19; execution-panel acceptance still follows the order lifecycle gates.

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

The default stack runs the two-strategy synthetic paper scenario and remains waiting for input. The tools-profile `validate` service checks an instance mandate; `tests` runs the full suite. Use the separate provider and operations runbooks for delivered S5–S7 commands. S8 remains unimplemented.

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
| S5 | Verified broker data and read-only shadow runtime | IN_PROGRESS | Provider contract evidenced; no execution path enabled |
| S6 | Autonomous demo order lifecycle | IN_PROGRESS | End-to-end demo and fault suite pass with reconciled exposure |
| S7 | Operable release: controls, deployment and recovery | IN_PROGRESS | Restore/restart/upgrade drills and dashboard evidence complete |
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

### F5.1 — cTrader authentication and account binding — DONE

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

### Delivery F5.4 — implementation slice

Branch: `feature/shadow_integration`. Status: IN_PROGRESS. Completed separate authenticated snapshot gateway/core/worker wiring and bounded history pagination; failed token refresh now terminates safely. 104 tests and 4 subtests pass; shadow Compose validates. Actual provider qualification and incremental feed optimization remain open. Feature commit: `git log --all --grep="F5.4:"`.

### Delivery F6.2 — implementation slice

Branch: `feature/demo_pending_order_lifecycle`. Status: IN_PROGRESS. Added durable pending-order revisions and owned cancellation; delayed fills retain position exposure after remainder cancellation. 105 tests and 4 subtests pass. Actual broker lifecycle and core demo adapter remain unqualified. Feature commit: `git log --all --grep="F6.2:"`.

### Delivery F6.3 — implementation slice

Branch: `feature/demo_protection_supervisor`. Status: IN_PROGRESS. Added opt-in demo protection supervisor with durable one-shot repair then owned-close requests, freshness and ownership gates, restart deduplication and no assumed closure. 106 tests and 4 subtests pass. Service activation and actual demo recovery await S5 qualification. Feature commit: `git log --all --grep="F6.3:"`.

### Delivery S5–S7 — release integration review (2026-10-16)

Branch: `feature/release_integration_review`. Added explicit verified hedged-account capability gating; netted accounts need a separate ownership adapter. Updated README and the handoff/remaining-work matrix to distinguish implemented components from incomplete stage acceptance.

Observed final local checks:

- Runtime, test, gateway-check and gateway Docker targets built successfully on local ARM64 Linux containers.
- Installed gateway-check image: **107 passed, 4 subtests passed**.
- Installed base/test image: **98 passed, 7 SDK-dependent skips, 4 subtests passed**. The gateway image exercises those SDK paths.
- Resolved paper Compose isolation audit: **PASS**, five services. Shadow analysis Compose configuration validation: **PASS** using placeholder paths/account, without opening a broker session.
- Docker restart drill: **PASS**; core killed with open exposure, workers and simulator restarted, same two command IDs closed, both instances READY at cursor 4, zero positions/reservations/rejections. Only the generated test project's volumes were removed.
- Earlier measured backup/restore and 60-second soak evidence remains in `docs/evidence/s7-local-drills.json`; not rerun without relevant changes. Browser visual acceptance and remote-host qualification remain unverified.

No actual broker session or trade was run. S5/S6/S7 remain IN_PROGRESS; F6.4 remains BLOCKED. The next required gate is read-only provider qualification with local credential files and an explicit demo account. The integrated demo service must subsequently be implemented against those verified contracts, then tested under explicit demo-order authorization. Do not mark these stages complete or enable real orders based on synthetic tests. Publication/CI results are recorded separately after observing them.

### Delivery F5.3 — implementation slice

Branch: `feature/incremental_feed_repair`. Status: IN_PROGRESS. Added incremental overlapping history queries, one subscription per connection generation and full reconnect backfill; incomplete history cannot advance the cursor. 108 tests and 4 subtests pass. Previous release CI passed on AMD64 and ARM64 (run 38824095895); actual provider streaming remains unverified. Feature commit: `git log --all --grep="F5.3:"`.

### Delivery F6.1 — implementation slice

Branch: `feature/demo_core_adapter`. Status: IN_PROGRESS. Implemented bound demo core adapter sharing strategy/risk/outbox, fenced controller and durable broker-event projection; unknown settlements retain risk and management acknowledgements require broker confirmation. 112 tests and 4 subtests pass, including offline protobuf accept-fill-close and uncertain-send restart. User requires offline tests only; actual orders remain disabled. Feature commit: `git log --all --grep="F6.1:"`.

### Delivery F6.3 — implementation slice

Branch: `feature/demo_service_wiring`. Status: IN_PROGRESS. Wired authenticated demo TCP server, reactor dispatch factory, isolated core service cycles and recovery supervisor calls. Full offline lifecycle now crosses real framed TCP; wrong token and stale fence rejected. 112 tests and 4 subtests pass. No enabled real-order launcher or broker connection was used. Feature commit: `git log --all --grep="F6.3:"`.

### Delivery F7.4 — implementation slice

Branch: `feature/encrypted_secret_recovery`. Status: IN_PROGRESS. Added offline AES-256-GCM secret archives with separate keys, private regular-file checks, authenticated restore before plaintext creation and exclusive destinations. 114 tests and 4 subtests pass; tests used synthetic secrets only. Actual off-host/key recovery remains outside current offline scope. Feature commit: `git log --all --grep="F7.4:"`.

### Delivery F6.2 — implementation slice

Branch: `feature/demo_integration_hardening`. Status: IN_PROGRESS. Hardened ownership with full order identity matching and position binding; management/recovery require fresh verified reconciliation. 115 tests and 4 subtests pass, including correlation collisions and stale TCP requests. Actual broker orders remain disabled under the users offline-only instruction. Feature commit: `git log --all --grep="F6.2:"`.

### Delivery — outstanding offline implementation verified (2026-10-16)

Branch: `feature/offline_release_evidence`. User mandate: implement/test offline and leave actual broker orders disabled. The earlier demo-adapter implementation deferral is superseded by F6.1a/F6.2a/F6.3a; provider-specific economics and actual activation remain gated. Added strict unknown-external-exposure and settlement-completeness checks and documented the provider boundary in `docs/demo-provider-boundary.md`.

Final observed evidence:

- Built runtime, base test, gateway-check and gateway images with installed packages.
- Installed gateway suite: **115 passed, 4 subtests passed**. Installed base suite: **102 passed, 10 dependency-related skips, 4 subtests passed**. Gateway suite exercises those dependency paths.
- Full offline protobuf entry acceptance, fill and settlement-gated closure pass over authenticated TCP. Uncertain sends survive core restart without duplication; wrong token/stale fence/stale management requests are rejected.
- Encrypted secret backup/restore tests use synthetic secrets only and verify tamper/wrong-key/path/permission/overwrite handling.
- Docker open-exposure restart drill: **PASS**, same two original order IDs, both instances READY at cursor 4, zero positions/reservations/rejections.
- Isolated paired paper restore: **PASS**, zero lost committed events, retained restore halt, two original orders, zero remaining positions; measured recovery **0.0081 seconds** against the predeclared 10-second limit.
- Resolved Compose isolation audit: **PASS**. Dashboard HTML and authenticated proxy verified inside the isolated private network: paper mode, stale indicator, two closed orders, zero exposure. Host/browser visual acceptance remains unverified: the browser plugin had a native dependency mismatch, and the alternate UI connection stalled and was interrupted. No screenshot acceptance is claimed.
- Previous published develop CI run `38824095895`: **success**, including native AMD64 and ARM64 jobs. Current publication CI is separate evidence, to be inspected after push.
- Only generated test-stack containers/volumes were cleaned up. No actual broker credentials, connection, order, host deployment, registry publication or off-host transfer was used.

The offline scope is delivered. Remaining parent-stage gates are actual provider/metadata/valuation qualification, explicit demo-order authorization and operational gateway bootstrap, intended-host release/restore/soak and visual dashboard acceptance. They are not marked DONE and should not be activated under the current offline-only mandate.

### Delivery F5.2a — validated economics inputs (2026-10-16)

Branch: `feature/verified_valuation_inputs`. **DONE** for the provider-independent boundary. Added strict valuation and settlement schemas and exporter with exact signed account-currency cash movements, unique allocation, lifecycle coverage, quantity completeness, evidence hashing and freshness checks. Docker offline targeted tests: **12 passed**. Actual broker economics mapping/qualification remains open; no credentials or orders used. Next: gateway lifecycle and reconnect orchestration using injected offline provider adapters.

### Delivery F6.3b — operational lifecycle assembly (2026-10-16)

Branch: `feature/gateway_lifecycle`. **DONE** for injected-provider lifecycle. Added disabled-by-default component assembly, SDK execution callback persistence, cold/reconnect reconciliation, event/generation race invalidation, freshness checks, and RPC/reactor shutdown. Docker tests: **9 lifecycle tests passed**, including real reactor/thread shutdown; existing TCP demo integration also passed. No credential loader, enabled order deployment or raw broker economics/history mapper claimed. Next: reproducible offline release bundle and visual dashboard acceptance retry.

### Delivery F7.3a — reproducible paper release handoff (2026-10-16)

Branch: `feature/offline_release_bundle`. **DONE** for offline packaging tooling. Added committed-source allowlist, exact Git revision and SHA256 file manifest, immutable image override, clean-tree/exclusive-destination checks and verification against tampering, extra files, traversal, symlinks and incomplete output. Docker targeted tests: **6 passed**. Bundles explicitly remain paper-only and do not claim registry publication; only public fixture tokens included. Real registry/host/backup destinations still required for external acceptance.

### Delivery F6.3c — bounded shutdown drain (2026-10-16)

Branch: `feature/gateway_shutdown_drain`. **DONE**. Shutdown waits for in-flight provider reconciliation before storage can close; the observation remains invalid. A 20-second timeout fails shutdown explicitly and preserves database ownership. **11 lifecycle tests passed**, including stale collection rejection, real RPC/reactor shutdown, successful drain and stalled-provider timeout. Next: installed-image regression, tracker handoff and publication.


### Delivery — credential-independent follow-up handoff (2026-10-16)

Branch: `feature/offline_completion_handoff`. User requested all remaining work without broker credential dependencies. Completed on separately tested branches and merged to develop:

- F5.2a: strict provider-independent valuation/settlement input exporter, commit `328f7c2`.
- F6.3b: disabled gateway assembly, SDK callbacks, reconnect/history and observation race handling, commit `4679c8d`.
- F7.3a: reproducible paper release packaging and verification, commit `9788e90`. Also built and verified a bundle using actual committed Git blobs on the host; image digest deliberately a placeholder, not a publication claim.
- F6.3c: bounded in-flight shutdown draining, commit `205aa99`.

Final installed gateway image: **144 tests and 4 subtests passed**, network disabled. Installed base image: **120 passed, 11 dependency-related skips, 4 subtests passed**; gateway suite covers those paths. Resolved Compose isolation audit: **PASS**, five services. Browser skill retry failed on bundled native dependency ABI mismatch; alternate browser inventory contained only in-app browser and MCP Apps. Visual acceptance remains unverified. Previous successful CI `38855042847` is baseline evidence, not evidence for these new commits. New push/CI reported separately.

Remaining work is explicit: implement and qualify the selected broker's raw economics/history exporter; connect/read-only qualification; authorized actual demo lifecycle/fault tests; working-browser visual acceptance; selected registry publication, clean Linux-host deployment/soak, and off-host recovery. Registry/host/backup destinations requested asynchronously; none assumed. S5/S6/S7 remain IN_PROGRESS, F6.4 BLOCKED; S8 outside current scope. No actual broker session/order, registry image publication, remote host deployment or off-host secret transfer occurred.

### Delivery F5.1a — sandbox credential intake (2026-10-16)

Branch: `feature/sandbox_provider_qualification`. User now authorizes sandbox credential use for dependent implementation/read-only qualification. Actual orders remain disabled under the earlier explicit instruction. Found untracked `Sandbox.rtf`, restricted it to 0600 and excluded Sandbox documents from Git and Docker context. No secret values printed or committed. Added private credential import with synthetic tests; copied relative expiry forces refresh rather than inventing an issuance time. Actual connection currently blocked: document contains access/refresh tokens but no application client ID/client secret. Requested only the local application-credential path. Continue account economics and qualification tooling while awaiting it.

### Delivery F5.2b — raw cTrader account economics (2026-10-16)

Branch: `feature/ctrader_account_economics`. DONE for the supported protocol mapping. Added exact deposit-currency balance, server net unrealized P&L, summed used margin and conservative free margin. Supports HEDGED/SUM/no-bonus profile only; other account profiles remain blocked. Bracketed collection rejects changed account records, stale timing, reconnect races and incomplete P&L. Targeted Docker tests: **16 passed** including session gates. Actual account mapping remains unqualified until application credentials are available. Next: read-only discovery/qualification runner and provider settlement mapping.

### Delivery F5.1b — sandbox read-only probe (2026-10-16)

Branch: `feature/sandbox_readonly_probe`. DONE for tooling; actual run blocked by missing application credentials. Added demo-only discovery, forced private refresh, explicit account selection when ambiguous, bounded metadata/history/account-economics collection and exclusive private evidence output. Targeted tests: **2 passed**; pinned SDK P&L request availability verified. Reports distinguish collected evidence from full qualification and expose no auth payloads. Next: audited settlement adapter; then run actual probe once application file path is provided.

### Delivery F6.2b — raw deal settlement mapping (2026-10-16)

Branch: `feature/ctrader_settlement_mapping`. DONE for audited-profile mapping. Added raw deal-to-settlement normalization with original entry binding, exact lifecycle quantities, opening/closing fees, explicit fee signs and no double-counted closing commission. Missing cost fields, partial history, scale-ins, duplicate deals, foreign/expired policies reject. **10 Docker tests passed**. Actual fee convention/profile qualification remains blocked on application credentials and broker evidence; no guessed policy or orders enabled. Next: connect raw provider history/economics to the existing lifecycle.

### Delivery F6.3d — provider history/lifecycle integration (2026-10-16)

Branch: `feature/ctrader_provider_reconciliation`. Implemented raw bounded history, original-order matching, external exposure detection, settlement-backed closure, pending-remainder rejection and ledger-before-settlement checkpoint ordering. Targeted provider and lifecycle Docker checks: **14 passed**. Actual provider acceptance and broader installed-image regression remain pending.

### Current sandbox handoff — approval service blocked (2026-10-16)

The user supplied the repository directory as the application-credential location. Found `CtraderInt.rtf`; parsed the application ID/secret locally without displaying values. Both it and `Sandbox.rtf` are 0600 and excluded from Git/Docker builds. Private combined credentials are prepared at `var/sandbox-private/credentials.json`; application-only JSON is beside it. Do not print these files, commit them, include them in build contexts, or overwrite future rotated tokens with the old document. Copied relative token expiry forces refresh. No broker connection or order has occurred.

The next Docker validation command was rejected before execution because automatic approval review hit its usage limit. The error explicitly said this was a review failure, not a safety determination. Do not bypass that gate. An already-running provider/lifecycle test completed with 14 passes. A proposed additional cache-restart test command was not executed; no claim is made that it passed.

Next actions after approval capacity is restored: run full gateway/base Docker regressions, build the gateway image, invoke the read-only probe with private mounts and exclusive output/rotation paths, discover and bind the actual demo account (ask selection only if multiple), inspect actual metadata/economics, qualify contract and fee profiles, complete streaming/reconnect/shadow and provider integration acceptance. Orders remain disabled; actual demo lifecycle tests still need explicit authorization superseding the earlier no-orders instruction. Push the tested feature/develop commits and inspect CI. Registry/host/off-host destinations remain separate pending inputs.

### Delivery F5.1c — actual sandbox connection acceptance (2026-10-16)

Branch: `feature/sandbox_connection_acceptance`. Application authentication and refresh rotation succeeded against verified demo TLS. User selected account 48232468 from three demo accounts. Fixed duplicate application authentication after discovery; reconnect still performs full authentication. Added redacted staged probe diagnostics and a durable settlement cache/restart test.

Actual read-only account authentication, exact EURUSD/XAUUSD symbol selection, metadata and 24-hour M1 history retrieval succeeded (1,341 bars per symbol). Economics collection failed closed with STALE_ACCOUNT_ECONOMICS. Observed profile is HEDGED/MAX, also outside the current HEDGED/SUM mapper. Neither margin semantics nor freshness limits were relaxed. Full qualification remains incomplete. Sanitized evidence: `docs/evidence/demo-connection-acceptance.json`; raw reports remain private in `var/sandbox-state/`.

Verification: targeted session/probe/provider tests **9 passed**; full source gateway suite **175 passed, 4 subtests passed**. Earlier installed gateway suite **174 passed, 4 subtests passed**; installed base **132 passed, 14 dependency-related skips, 4 subtests passed**. The newest authentication correction is source-tested; rebuilt installed-image acceptance remains pending. No actual broker order was sent.

This supersedes the approval-service blocker above. Preserve rotated `var/sandbox-state/tokens.json`; never seed it again from the old document. Next: verify MAX margin aggregation semantics, implement explicit profile support with tests, resolve the five-read valuation freshness window without weakening stale-data gates, then repeat probe using a new exclusive output filename (probe-004.json next). Streaming/reconnect/shadow, fee/conversion/contract qualification and authorized demo order acceptance remain open.

### Delivery F5.2c — MAX margin and bounded valuation latency (2026-10-16)

Branch: `feature/max_margin_valuation`. Supports HEDGED/MAX by summing margins by symbol and side, then summing the larger side for each symbol. NET and unknown grouping remain rejected. SDK queue drains one request per 260ms (below 5 historical requests/sec) instead of one-second batches; independent bracket reads overlap. Two-second freshness, unchanged-record and generation checks remain enforced. Official semantics: https://help.ctrader.com/ctrader-algo/references/Account/TotalMarginCalculationType/ .

Targeted Docker regression: **25 passed**. Actual read-only probe `var/sandbox-state/probe-004.json`: **COLLECTED**, including account economics within the unchanged freshness gate, EURUSD/XAUUSD metadata and history. Selected account had zero positions, so multi-position MAX aggregation is protocol-tested with synthetic fixtures, not claimed observed on this account. No orders enabled. Next: capability evidence and actual streaming/reconnect/shadow qualification.

### Delivery F5.2d — account-specific capability audit (2026-10-17)

Branch: `feature/provider_capability_audit`. Added `probe --audit`: bounded complete bid/ask tick samples, strict delta decoding and exact completed-bar OHLC comparisons, account/symbol-bound expiring capability reports and explicit remaining execution blockers. Docker targeted tests: **10 passed**. Actual `probe-006.json`: three completed M1 bars per EURUSD/XAUUSD matched bid OHLC and differed from ask; account type, symbol IDs and volume grids observed. Sanitized evidence: `docs/evidence/demo-capability-audit.json`. Tick price delta decoding is observed against bar OHLC; no broker tick-grid inference is made from observed price increments or digits.

Capability audit is delivered; full execution qualification remains open: tradable tick grid, contract-value policy, complete commission/conversion policy, fresh prospective margin, protection sides, order/expiry behavior and current session state. Metadata fee fields are evidence only, not an audited settlement policy. Read-only feed basis is supported for the sampled account/symbols; streaming/reconnect validation follows.

### Delivery F5.3b / F5.4b — bounded read-only shadow acceptance (2026-10-17)

Branch: `feature/readonly_shadow_acceptance`. Implemented read-only wire allowlist/audit, bounded service runtime, forced TCP reconnect, immediate disconnect coverage invalidation, in-flight collection drain and private exclusive acceptance reports. Reporting separates reconnect success from fresh market coverage; unknown/mutating wire calls reject. Operations runbook documents isolated Compose execution, private state and required warm-up data.

Tests: session/feed/shadow targeted **13 passed** before drill; final installed gateway **188 passed, 4 subtests passed** including report classifications. Actual installed four-container stack: gateway, core and two authenticated healthy workers. Drill requested 90 seconds, with bounded shutdown drain; exit **0**. Reconciliations **9**, generations **1 and 3**, application/account authentication twice, subscriptions twice, cached bars **744**, spot events **4**, failures **0**, order writes **0**. Core had 2 registered instances and **0 events/decisions/commands/reservations**. Sanitized evidence: `docs/evidence/demo-shadow-acceptance.json`; private raw report `var/sandbox-state/shadow-run-001.json`. Only this uniquely named test stack was stopped; private state retained.

Outcome: actual reconnect/authentication/subscription/history/account recovery demonstrated; F5.1 DONE. Full F5.3/F5.4 acceptance is **BLOCKED_FRESH_COVERAGE**, not passed. Quote source times were 2026-10-16 20:59:34/35 UTC, over two hours before the run. Four subscription snapshots do not prove live updates. Do not alter source timestamps, invent closed intervals, replay as current data, relax freshness or claim strategy evaluation. Next: rerun with fresh quotes and complete required history (same rotated token store, one gateway writer, new report filename). Continue missing broker capability qualification independently; actual orders stay disabled.

### Delivery F5.4c — strategy-derived shadow configuration (2026-10-17)

Branch: `feature/strategy_shadow_configuration`. DONE for configuration tooling. Reviewed strategy manifests now declare history and price basis. The shared generator unions requirements by instrument/basis/timeframe, validates digest/account/mode and expiring observed symbol/basis evidence, and hashes the complete configuration. Gateway checks it before startup and each poll. Updated preparation CLI requires `--probe` and generates `feed.json`; Compose mounts that generated file. No strategy rules are embedded in the shared generator.

Docker targeted tests: **14 passed**, including arbitrary strategy names, max-history union, stale evidence, changed requirements, mismatched account/package/mode and wrong basis. Offline private probe-to-config smoke passed with two instances and four history intervals. Full fresh-market shadow acceptance remains pending. Next: dashboard browser acceptance, broker cost/contract mappings, and recovery fault tests.

### Delivery F7.1a — dashboard provider attribution and Chrome acceptance (2026-10-17)

Branch: `feature/dashboard_acceptance`. DONE for read-only UI slice. Gateway/core propagate connection generation, coverage and capability blockers to an allowlisted status response. Provider observations expire after 30 seconds; RPC failures surface unavailability. Chrome acceptance covered paper decisions/evidence, stale data, invalid authentication and a clearly labelled synthetic shadow fixture with incomplete coverage and blockers. Screenshot: `docs/evidence/dashboard-chrome.png`. The in-app browser still has a native ABI loading failure; Chrome fallback works. Targeted Docker checks: **5 passed**. Actual fresh broker panel acceptance remains dependent on the fresh-market run; synthetic UI evidence does not qualify broker capabilities.

### Delivery F5.2e — prospective cost arithmetic (2026-10-17)

Branch: `feature/broker_cost_mapping`. DONE for offline arithmetic, with **6 Docker tests passed**. Added all four precise commission types/minimums, account-bound fresh conservative FX conversion, and correlated exact-volume expected margin. Explicitly rejects tier extrapolation, missing paths and ambiguous identities. Contract export remains pending audited multiplier/tick/fee incidence and nonlinear sizing integration; these helpers do not mark capabilities qualified or enable orders. See demo-provider boundary for supported inputs and limitations. Next: recovery fault drills and full regression.

### Delivery F7.4b — interrupted restore drills (2026-10-17)

Branch: `feature/recovery_failure_drills`. DONE for local failure handling. Paired paper restore now stages the core database until the paired broker copy and durable entry halt exist, and retains an INCOMPLETE marker on failure. Added injected disk-failure tests for paired state and encrypted synthetic secrets, plus incompatible-manifest rejection. **7 targeted Docker tests passed** including successful halted restore and no-overwrite recovery. Failed destinations are retained for inspection; retry into a new isolated directory. Actual off-host recovery and intended-host soak still need destinations and evidence.

### Delivery — offline follow-up handoff (2026-10-17)

Completed and merged separately: strategy-derived configuration `4c8770e`, dashboard/Chrome acceptance `28457d3`, prospective cost arithmetic `f2891e3`, interrupted restore hardening `f8c481c`. Final rebuilt installed gateway suite: **207 passed, 4 subtests passed**, network disabled. Chrome screenshot uses synthetic fixture data. No credentials or orders used in this follow-up. Publication and CI are checked after this commit; do not treat the earlier baseline CI as verification of these changes.

Next: fresh-market shadow run with new exclusive report filename and preserved rotated token store. Verify real quote updates, sufficient warm-up history, decisions and zero writes. Contract qualification still requires audited multiplier/tick/fee incidence, nonlinear sizing integration and fresh conversions/margin. Demo order lifecycle acceptance needs explicit authorization. Intended Linux host, registry and off-host backup destination remain unspecified. S5–S7 stay open; S8 remains unstarted.

### Delivery F4.2a / F5.2f — exact-quantity nonlinear sizing (2026-10-17)

Branch: `feature/nonlinear_quantity_sizing`. Added account/proposal-bound, two-second-fresh exact quantity cost and margin tables. Core selects the largest evidenced feasible quantity without interpolation; minimum fees and nonmonotonic margin are supported. Exact tables cannot mix with per-unit cost defaults. Valuation rejects foreign/expired tables; the demo send boundary rechecks serialized size against current economics before transport. Existing linear paper contracts remain supported. Targeted Docker regression: **20 passed**, including both linear and exact-cost offline TCP accept/fill/settle lifecycles, minimum-fee budgets, margin tiers, invalid grids, stale/foreign observations and tampered size rejection. Actual broker qualification remains open. Next: strict audited contract assembly from explicit cost bounds and correlated margin evidence.

### Delivery F5.2g — audited contract assembly and proposal quoting (2026-10-17)

Branch: `feature/audited_contract_assembly`. DONE for offline assembly/integration. Explicit audited policy supplies tick/volume grid, multiplier and complete round-trip upper cost bounds; correlated margin evidence supplies only exact requested volumes. Assembly binds account, proposal, source hashes and freshness without upgrading capability evidence. Added fenced proposal-contract RPC, optional injected quote callback in disabled lifecycle assembly, and demo runtime quoting after analysis with current execution time. Submission re-quotes and rejects changed economics. **36 targeted Docker tests passed** including lifecycle, restart and execution checks. An initial full regression found the old protocol fixture lacked the new RPC; updated it and reran relevant checks. Actual policy audit remains required; no credentials or orders used. Next: read-only margin quote collector and installed-image regression.

### Delivery F5.2h — read-only prospective margin collector (2026-10-17)

Branch: `feature/prospective_margin_collector`. DONE for offline provider tooling. `MarginQuote` supplies the injected proposal quote callback using allowlisted expected-margin reads, exact integer normalization and explicit candidate volumes. Audited policies and conversions bind account/instrument/currencies; source freshness, generation and exposure revision guard requests and bounded evidence reuse. **16 targeted Docker tests passed**, including in-flight reconnect, exposure change, disconnect, timeout and foreign conversion rejection before transport. No actual provider request/order used. Actual policy/conversion inputs and fresh broker qualification remain open.

### Delivery — offline economics completion handoff (2026-10-17)

Feature commits: nonlinear sizing `726a3b7`, audited assembly/proposal RPC `7b7909e`, read-only margin collector `db03931`; each tested and merged separately from develop. Rebuilt installed gateway suite: **225 passed, 4 subtests passed**, networking disabled. No actual broker connection or order occurred. Publication/CI checked after this handoff commit; local suite is not a CI result.

The previously outstanding offline nonlinear sizing and contract assembly are delivered. Runtime consumes proposal-specific quotes and validates them at send time; collector is injected only with explicit audited policy, conversion source, candidate volumes and an exposure revision provider. Missing inputs continue to block. No default broker policy, candidate schedule or currency conversion is invented.

Next concrete work: qualify actual account/symbol tick and multiplier, complete fee/conversion policy and protection/order capabilities; supply reviewed quote inputs; rerun fresh-market streaming/shadow and actual panel acceptance. Actual demo lifecycle tests still need explicit order authorization. Registry, intended Linux host and encrypted off-host destination remain unspecified. These are distinct gates: fresh market data alone does not complete S5–S7. S8 remains unstarted.

### Delivery F5.2i — active-market quote-basis audit (2026-10-18)

Branch: `feature/fresh_market_acceptance`. Actual EURUSD reopening exposed a candle-open mismatch when the ask changed before the bid. Audit now reconstructs each side at the first observed bid-or-ask event, carrying only a known predecessor tick from the bounded prior minute. Missing predecessor or conflicting same-time ticks reject; all four OHLC values must still match exactly. Added OHLC diagnostics. **9 targeted tests passed**. Actual read-only probe-010: three completed EURUSD bars match reconstructed bid OHLC and differ from ask; probe-007 found no XAUUSD bars in the 24-hour window. Public evidence: `docs/evidence/fresh-candle-audit.json`. Full execution qualification remains open; orders disabled. Next: bounded streaming/reconnect run with newly generated evidence. TPR warm-up spans a weekend gap and is not assumed complete.

### Delivery F5.3c / F5.4d / F7.1b — fresh shared-runtime acceptance (2026-10-19)

Branch: `feature/selective_shadow_acceptance`. Added explicit `prepare_shadow --instances` selection; manifests and TPR warm-up requirements remain unchanged. One-sided spot updates now retain independently observed bid/ask values with the OLDEST side timestamp; disconnect clears both caches. No freshness relaxation. **24 targeted Docker tests passed** including selection and side freshness.

Actual XAUUSD timer-fixture drill: **PASS**, exit 0; 287 spot events, 12 reconciliations, 6 complete snapshots, generations 1 and 3, zero failures/order writes. Core recorded 14 events/decisions (1 fixture ENTRY, 13 NO_ACTION), zero commands/reservations. Chrome verified real-data provider status, generation-3 complete coverage, zero exposure and original decision evidence. Sanitized report `docs/evidence/fresh-shadow-acceptance.json`; screenshots `live-shadow-status.png` and `live-shadow-dashboard.png`. Private report `shadow-run-003.json`. Earlier EURUSD run-002 remained blocked on freshness and is not a pass. Both EURUSD/XAUUSD current three-bar bid audits passed in probe-011.

This completes bounded shared streaming/reconnect and timer shadow acceptance, not TPR or full S5 acceptance. TPR's 16 H1 and other contiguous histories still span the weekend gap; no closure intervals or bars were fabricated. Next: read-only exact-quantity margin evidence, full regression and publication. Orders remain disabled.

### Delivery F5.2j — exact-volume margin qualification runner (2026-10-19)

Branch: `feature/observed_margin_qualification`. Added `probe --margin-audit` to request BUY/SELL expected margins at up to three explicit volume-grid candidates per symbol, normalize exact money scales, bind correlated requests and enforce the unchanged two-second observation window. No order calls, extrapolation or automatic capability promotion. **16 targeted Docker tests passed** (host overload stretched runtime to 369.64 seconds). Actual probe-012 failed closed during account economics with STALE_ACCOUNT_ECONOMICS before margin qualification. Margin observations are therefore still unqualified. Preserve the rotated token store and failed report; retry only when host latency is healthy. No broker orders enabled.

### Delivery handoff — fresh-market acceptance (2026-10-19)

Branches `feature/fresh_market_acceptance`, `feature/selective_shadow_acceptance` and `feature/observed_margin_qualification` were tested and merged separately into develop. Final installed Docker regression: **229 passed, 4 subtests passed in 18.68 seconds**, network disabled.

Read-only probe-013 succeeded after host latency recovered: EURUSD quantities 1,000/2,000/3,000 and XAUUSD quantities 1/2/3, with BUY/SELL margin observations in USD. Request-to-check latency was approximately 0.110s and 0.505s respectively, inside the unchanged two-second gate. Sanitized evidence: `docs/evidence/observed-margin-audit.json`. This establishes sampled expected-margin behavior only; observations expire and cannot substitute for fresh proposal-bound quotes or certify untested quantities, cost policy or order capabilities. Private probe-012 retains the earlier overload failure.

Actual shared-runtime shadow acceptance remains bounded to the timer fixture: 287 spot events, 12 reconciliations, six complete snapshots, forced reconnect, 14 decisions and zero order writes. Chrome evidence is in `docs/evidence/live-shadow-status.png` and `live-shadow-dashboard.png`. Acceptance containers have been removed; no ongoing shadow process is implied.

Remaining: full contiguous TPR history and strategy shadow acceptance; audited tick grid, multiplier, complete fee/conversion policies and session/protection/order/expiry capabilities; explicitly authorized demo order lifecycle acceptance; intended Linux host, registry and encrypted off-host recovery qualification. S5–S7 remain partial and S8 unstarted. No order activation. Next: check all manifest history windows before a new both-strategy shadow run; use exclusive report paths and preserve rotated tokens.

### Delivery F7.3b — selected local demo host (2026-10-19)

DONE for local prerequisite tooling on `feature/local_demo_host`. User selected the current system for demo infrastructure. Added read-only Docker prerequisite checks and local exact-image Compose overrides, with fail-closed Linux/native architecture/non-root/resource checks. Registry publication and a separate Linux host are no longer local demo prerequisites. Two targeted container tests passed; actual installed-image host prerequisites passed. Host sleep is enabled; documented session-scoped wake assertion without changing global settings. Local paper soak passed: 300 events/60.07s, p95 317.8ms, RSS 38.94MiB, zero residual positions/risk. Isolated recovery passed in 0.020s with zero lost committed events, zero remaining positions and the restore halt preserved. This does not qualify broker execution or authorize orders.

### Readiness for first actual demo order test

Before requesting order authorization: establish fresh full-strategy shadow acceptance, audit exact symbol tick/value and complete fee/conversion policy, qualify current sessions and supported order/protection/expiry parameters, and prepare a bounded isolated test deployment with exclusive account ownership and persistent recovery state. Sampled margin checks already passed; every order still requires fresh proposal-bound margin/economics. Use this Mac with exact tested images and an attended awake session.

Then obtain explicit authorization for the concrete demo-only test scope (account, symbol, maximum quantity/exposure, duration, stop protection and cleanup). Actual entry/fill/protection/exit, observed fees, cancellation races and restart reconciliation are acceptance results of that test phase, not prerequisites that can be claimed from read-only checks. Autonomous demo operation follows successful lifecycle acceptance; live trading is outside this mandate.

### Delivery F5.3c — actionable shadow coverage diagnostics (2026-10-19)

DONE for diagnostics on `feature/shadow_coverage_diagnostics`; 14 targeted Docker feed/session tests passed. Shadow reports now retain the last exact per-symbol/timeframe contiguous count, required count and first missing bar, independently from quote age and reconnect repair status. Diagnostics use the same selection as the readiness gate; no extra closures, old quotes or fabricated bars are accepted. This makes the TPR warm-up blocker inspectable rather than reporting only a false coverage flag.

First actual order qualification scope is documented in `docs/demo-order-test-plan.md`; this is preparation, not activation or authorization.

### Delivery F5.3d — full-history shadow and quote clock diagnosis (2026-10-19)

Branch `feature/full_strategy_shadow_acceptance`. Installed Docker regression before quote instrumentation: **233 passed, 4 subtests passed**. Full XAUUSD TPR/timer run-004 collected all 400 M1, 80 M5, 24 M15 and 16 H1 required contiguous bars, 441 spots and 12 account reconciliations; forced reconnect passed. Zero core decisions/commands/reservations/positions: repair gate remained blocked. Evidence: `docs/evidence/full-shadow-004.json`. This supersedes the warm-up blocker, but does not establish full strategy acceptance.

Added bounded fixed-label quote rejection counters without exposing raw payloads or relaxing validation; **15 targeted feed/session tests passed**. Read-only run-005 identified **123 FUTURE_QUOTE rejections out of 140 spot events**. Host SNTP reported +0.062964 +/-0.026129 seconds against time.apple.com. A noninteractive synchronization attempt could not run because administrator authentication is required; the user has been asked to synchronize locally without sharing a password. Evidence: `docs/evidence/quote-clock-diagnostics.json`. Recheck host and Docker guest clocks and repeat full strategy acceptance after correction; no future-time tolerance was added.

The actual broker was identified from the selected-account profile. Public specification review is in `docs/evidence/broker-specification-review.md`; it corroborates some fields but leaves account-specific tick/fee/protection/expiry policy unresolved, including the displayed gold volume-step discrepancy. No credentials or account balances are in public evidence. Both diagnostic runs have ended; orders remain disabled.

Final installed regression including quote diagnostics: **234 passed, 4 subtests passed in 6.20 seconds**, networking disabled. Five Docker guest/host receive-time samples were within 2.1–2.9ms (including stdout delay), so no material additional guest drift was observed; this is not a clock synchronization proof. The host administrator synchronization request remains pending. No broker connection is left running. Tested changes are merged/published under the existing per-feature workflow; inspect the new develop CI separately from local results.

### CI correction — optional SDK test boundary (2026-10-19)

DONE on `feature/optional_sdk_test_guard`. CI run 39266453830 failed in the paper-only image because the new quote-rejection test imported Twisted without the existing optional cTrader SDK guard. Added the same importorskip guard as the other SDK tests; the gateway suite still executes it. Paper-only installed suite: 163 passed, 18 skipped, 4 subtests passed. Gateway feed tests: 8 passed; the diagnostic test executes there.

### F5.3e — independent quote recovery gate (2026-10-19)

DONE for implementation on `feature/quote_recovery_isolation`. Actual future quote rejections exposed a conflation of quote validity and historical repair. Add a durable quote-validity gate: rejected quotes block cached quote use and clear side observations, while completed history remains independently qualified. Both sides must be observed and valid before recovery; retained last accepted timestamps still reject regression. Real disconnect invalidates both history and quotes. Future-time and two-second freshness checks are unchanged.

Validation: 19 targeted feed/session/shadow integration tests passed. Installed gateway suite: **235 passed, 4 subtests passed**; installed paper-only suite: **163 passed, 19 optional-SDK skips, 4 subtests passed**. Actual run-006 after user-reported clock synchronization still rejected 390 future quotes out of 455 spots and had zero complete snapshots; reconnect passed. Preserve `docs/evidence/post-sync-shadow-006.json` as failed evidence. Re-run using the recovery fix; no future quote or stale quote is made valid by this change.

### F5.3f — per-side future timestamp boundary (2026-10-19)

DONE on `feature/quote_timestamp_bounds`; 20 targeted Docker feed/session/shadow tests passed. Review of partial quote recovery found that validating only the combined oldest timestamp could hide a future-dated update on the newer side. Reject each incoming side's timestamp before caching it. This tightens the existing future-time rule; no clock tolerance is introduced. Add a regression for a future bid arriving alongside an older valid ask.

### Delivery handoff — post-sync shadow acceptance (recorded 2026-10-20)

Branch `feature/post_sync_shadow_acceptance`. User confirmed clock synchronization; this supersedes the earlier outstanding administrator request. On 2026-10-19 run-007, the corrected stack produced **6 events and 12 decisions**: TPR **6 WATCH**, timer fixture **1 ENTRY and 5 NO_ACTION**. Both instances evaluated three events after the forced-disconnect time, and the gateway confirmed reauthentication/reconciliation across generations 1 and 3. Commands, reservations, positions and actual order writes were all zero. Evidence: `docs/evidence/full-strategy-shadow-007.json`. A fixture ENTRY is a recorded decision only.

The gateway's bounded report status is PASS, with 409 spot events, 12 reconciliations and one complete polled snapshot. **370 future quote rejections remain**; this is not sustained operational readiness or proof that clock mismatch is resolved. History warm-up and the quote/history recovery bug no longer block the bounded functional path. Future events, incomplete side observations, regressing timestamps and stale quotes remain rejected. Parent S5–S7 stages remain partial.

Final installed regression: **236 gateway tests + 4 subtests** in 5.98s; **163 paper tests, 20 optional-SDK skips + 4 subtests** in 2.80s. The prior CI failure was corrected on `feature/optional_sdk_test_guard`; recovery and per-side timestamp fixes were separately tested, committed and merged from develop. The completed run-007 containers/networks were removed on 2026-10-20, retaining private evidence and rotated tokens. Other workloads were untouched.

Next: inspect new CI, resolve residual timestamp mismatch with measured evidence and qualify sustained quote availability, then finish selected-account execution policy audit. Existing feed audits expire: refresh through a new private probe before another actual run. First demo order testing still awaits these gates, the bounded deployment's final validation and explicit authorization of the prepared test scope in `docs/demo-order-test-plan.md`. No orders have been enabled.

### F5.2k — normalized volume evidence interoperability (2026-10-20)

DONE on `feature/normalized_volume_evidence`; 24 targeted Docker tests and the installed gateway suite (237 passed, 4 subtests passed in 4.48s) passed. A new offline integration regression reproduced an audit/transport mismatch: the audit emitted Python repr with protocol field names, while fenced preparation requires JSON min/max/step in normalized units. Emit canonical JSON in the existing consumer schema. The test passes audited quantities through order preparation using an otherwise synthetic qualification fixture and rejects off-step quantity; it sends no order and does not promote actual capabilities. Historical reports remain unchanged; regenerate expired/new qualification evidence rather than rewriting its hash.

### Current-day acceptance — clock correction confirmed by observations (2026-10-20)

Branch `feature/current_clock_feed_acceptance`. Host SNTP measured +0.001946 +/-0.009614 seconds. Probe-014 renewed sampled bid candle basis (three comparisons each for EURUSD/XAUUSD), account economics and exact-volume margin observations; no capability promotion or order calls. Sanitized summary: `docs/evidence/current-broker-probe-014.json`. Its volume-grid format predates F5.2k; retain the immutable private report and use a new probe for execution-policy inputs.

EURUSD full-strategy run-008 collected 36 spot events with **zero spot/timestamp rejections**; the final quote was valid and 0.289 seconds old, and forced reconnect passed. **Full coverage did not pass**: M1 had 73 of 400 required contiguous bars, first missing end 2026-10-19 23:38 UTC. The same 23:37–23:38 interval is absent from independent probe-014 history. M5/M15/H1 counts were complete and repaired. Do not classify the missing minute as a closure or fabricate a candle without evidence. Core made zero decisions and zero commands/positions/reservations. Evidence: `docs/evidence/current-clock-shadow-008.json`.

The Oct 19 bounded XAUUSD functional pass remains historical evidence, not a substitute for today's feed checks. The observed clock problem is no longer the immediate blocker; complete current history and selected-account execution policies remain required before preparing an actual demo order. All run-008 containers/networks were removed, private state/tokens retained. Source regression after grid fix: **237 passed, 4 subtests passed**. Published predecessor d24675b passed CI 39349709656. Keep demo orders disabled until the specific bounded test scope is ready and explicitly authorized.

### F5.2l — reproducible FxPro specification reconciliation (2026-10-20)

Branch `feature/fxpro_specification_reconciliation`. Adds account-bound, expiring public/account comparisons without capability promotion. User-supplied GOLD/XAUUSD mapping recorded. Fresh read-only probe-015 collected metadata, candle audits and exact-volume margins. EURUSD volume and both commission rates match; gold published step conflicts with API. Zero minimum commissions and P&L conversion fee rates observed for the selected USD account. Tick/rounding/settlement/order acceptance remain incomplete. Nine specification regressions plus six cost tests pass (15 total); an initial decimal string-format assertion was corrected to compare numerical values. No orders enabled. Next: current shadow acceptance and broker session interpretation.

### F5.2m — exact broker session schedule interpretation (2026-10-20)

Branch `feature/broker_session_schedule`. Interprets the selected account's UTC weekly intervals with Sunday origin and exclusive endpoints, trading-mode restrictions and dated/recurring holiday intervals. Unknown zones or applicable holiday boundaries remain UNKNOWN. Public rounded opening hours do not replace exact broker schedules. The report deliberately says SCHEDULED_OPEN, never an executable OPEN capability: current quotes/account state are separate. Seven boundary/holiday tests and nine specification tests pass (16 total). The private specifications-session-015 report retains the actual schedule review result; the later closure integration corrected handling of dated holidays in another time zone. Source: https://help.ctrader.com/open-api/model-messages/ . No order capability promoted.

### F5.3g — current-symbol shadow and targeted gap diagnosis (2026-10-20)

Branch `feature/current_symbol_shadow_qualification`. Added bounded exact-minute bar/bid/ask tick diagnosis to the read-only probe, rejecting incomplete/foreign responses and connection races. No candle fabrication, closure inference, freshness relaxation or capability promotion. Eight targeted gap/probe tests passed; installed full gateway regression passed **259 tests + 4 subtests in 5.03s**.

EURUSD run-009: 63 spots, zero quote rejections, 16 account reconciliations, forced reconnect PASS. Coverage remains blocked: M1 92/400, same missing minute ending 23:38 UTC; final quote age 4.041s also exceeded the unchanged two-second budget. One collection failure recorded. Core events/decisions/commands/reservations/positions all zero. Public evidence: `docs/evidence/current-eurusd-shadow-009.json`. Actual remaining runs/diagnostic results follow below.

XAUUSD run-010: 615 spots, zero quote rejections, 16 reconciliations and forced reconnect PASS. Final quote age 0.540s; history stops at the daily break ending 22:00 UTC (M1 194/400, M5 38/80, M15 12/24, H1 3/16). One collection failure; zero core events/decisions/orders. This identifies an additional integration limitation: exact UTC schedule interpretation is implemented, but verified historical closures are not yet wired through warm-up fetching and every snapshot consumer. Do not mark a closure from absence alone. Evidence: `docs/evidence/current-xauusd-shadow-010.json`.

Probe-016 gap diagnosis rejected because the pinned SDK's trendbar response has no `hasMore` field. Corrected the bounded one-minute audit to accept that verified response shape while rejecting explicit truncation and more than one M1 bar; tick responses still require explicit completeness. Eight targeted tests pass after correction. Probe-017 then succeeded: no bar and zero bid/ask ticks for 23:37–23:38 UTC, reported as NO_TICKS_REPORTED, not a market closure or repaired candle. Evidence: `docs/evidence/eurusd-gap-audit-017.json`. The previous Docker command was blocked by approval-review usage exhaustion; user resumed and the same normal approval path succeeded. No bypass was used.

### F5.3h — verified scheduled-closure integration (2026-10-20, DONE for implementation)

Branch `feature/verified_session_closures`. The bounded gap audit now supports up to 60 minutes. A closure needs both complete empty bar/bid/ask history and an exact account-symbol UTC weekly schedule with no overlap with an open interval. Evidence expires, remains bounded to recent historical intervals, and never promotes live session/order capabilities. The feed uses the same closure callback for repair and RPC snapshots, extending cold history lookback by the evidenced duration and counting only real bars. Unexplained gaps and partly open bars stay blocked. Holiday closures are not inferred; dated holiday checks now use their own time zone.

Probe-018 collected fresh candle/margin audits plus zero bars/ticks for XAUUSD 21:00–22:00 UTC on Oct 19. Initial certification rejected the presence of a historical Moscow-time holiday; regular weekly closures do not become open because of an additional holiday, so that overly broad rejection was removed and covered by regression. No timeframe counts or price freshness limits changed.

EURUSD run-011 now has complete history (400 M1, 80 M5, 24 M15, 16 H1), a bounded gateway PASS and reconnect PASS, 14 core events/28 decisions with zero commands/reservations/positions. However 73/93 spots were rejected as future-dated, only one complete polled snapshot occurred, and the last quote was invalid/stale. Host SNTP +0.023302 +/-0.009115s; continuous quote availability remains unqualified. Evidence `docs/evidence/current-eurusd-shadow-011.json`.

Final F5.3h acceptance: **45 targeted tests passed**; installed gateway **271 passed + 4 subtests in 6.37s**; paper-only **190 passed, 22 skipped + 4 subtests in 2.98s**. Actual XAUUSD run-012 verified all manifest histories (400/80/24/16), 16 reconciliations and forced reconnect across generations 1/3. Core recorded 20 events/40 decisions and zero commands/reservations/positions. History closure integration is accepted. Quote acceptance is NOT: 380/452 spots rejected as FUTURE_QUOTE, zero complete gateway polling snapshots, one collection failure; core briefly obtained valid snapshots between polls. Status remains BLOCKED_FRESH_COVERAGE. Public evidence: `docs/evidence/verified-closure-shadow-012.json` and `xauusd-closure-audit-018.json`. Local-host-007 pinned the exact runtime/gateway images and passed prerequisites.

Remaining execution distinction: the current TPR adapter emits executable proposals only in paper and uses stop-limit, while the first broker transport profile is protected limit/GTD. Autonomous TPR demo activation needs a separately qualified compatible execution profile and adapter integration; a first attended EURUSD limit test does not establish that strategy's autonomous execution. Do not silently convert a stop-limit strategy into a limit strategy. S5–S7 and S8 remain open as described above.

### Online validation round and bounded demo preparation (2026-10-20)

Branch `feature/online_validation_round`, evidence-only. Fresh probe-019 and separate 180-second both-worker shadow runs 013/014 completed with zero order writes. Full history and forced reconnect passed for both symbols; quote validity failed, correctly suppressing decisions. Installed gateway regression rerun: 271 passed + 4 subtests in 5.23s. Public sanitized evidence and comprehensive blocker matrix saved under `docs/evidence/online-*`. Prepared one-attempt EURUSD 1,000-unit protected limit/GTD test with proposed USD5/0.1%-equity planned-loss ceilings, final-price preview and explicit approval still required. No strategy or safety validator modified. This round does not close S5–S8.

### Post-sync diagnostic and macOS clock command correction (2026-10-20)

Branch `feature/post_sync_validation`. User reported synchronization done. Read-only Apple measurement +0.131878 +/-0.009694s and Cloudflare +0.132161 +/-0.016897s still show host lag. Docker guest samples fall within host request/response windows; these coarse samples do not prove submillisecond alignment. Installed macOS `sntp(1)` manual specifies `-s` only slews offsets below 50ms, while `-S` enables stepping larger offsets. Corrected operations instructions to `sudo sntp -sS time.apple.com`, with qualification stopped first. Reading network-time settings requires administrator access; no settings or clocks changed by the agent.

Fresh probe-020 COLLECTED. Diagnostic EURUSD shadow-015 (90 seconds, reconnect at35s) rejected98/100 quotes, zero complete snapshots,9 reconciliations, reconnect PASS, zero decisions/commands/reservations/positions/order writes. Evidence: `docs/evidence/post-sync-shadow-015.json`. Ten-minute acceptance was not attempted because the clock prerequisite failed. All diagnostic containers/networks removed; private token/evidence state preserved. Documentation/evidence only; `git diff --check` passed, no runtime source changed.

### Synchronized sustained acceptance (2026-10-20)

Branch `feature/synchronized_shadow_acceptance`, evidence only. Ten-minute EURUSD run-017 completed with full history, forced reconnect and 166 decisions but 466/596 FUTURE_QUOTE rejections: sustained acceptance FAIL. Post-correction host lag initially ~3.5ms, then ~17.8ms, finally ~21.7ms. Probe-021 could not qualify XAUUSD candle basis because a reconstructed bid close differed from its bar. Aborted setup run-016 is retained privately, not acceptance evidence. All drill containers removed. Detailed evidence: `docs/evidence/synchronized-shadow-acceptance.md`. `git diff --check` passed; no runtime changes or order writes.

### Quote-clock diagnostic aggregates — DONE (implementation) (2026-10-20)

Branch `feature/quote_clock_diagnostics`. Add bounded per-symbol count/min/max/total microseconds for source timestamps ahead of gateway receipt time, retained across reconnect and exported in the private run report. No raw messages, prices or credentials added; no timestamp tolerance or gate change. The metric is source timestamp lead, not a measured broker/NTP offset. Test exact microseconds, per-symbol separation, partial-side rejection, reconnect preservation and valid-message exclusion. Actual read-only diagnostic follows installed-image regression.

Diagnostic acceptance: installed gateway **272 passed +4 subtests in6.69s**. Local-host-008 pinned new gateway image and passed host prerequisites. Actual90-second EURUSD run-018:18 spots,13 FUTURE_QUOTE; source lead min10,912us,max18,802us,total190,380us (mean14,644.6us). Concurrent host measurement +0.021315 +/-0.006964s. These observations are consistent with remaining host lag, not proof of broker clock offset. Reconnect PASS;3events/6decisions; zero commands/reservations/positions/order writes. Report `docs/evidence/quote-clock-diagnostic-018.json`. All drill containers/networks removed; evidence/tokens preserved. User asked for read-only administrator time-setting outputs; no password requested or settings changed. No new timestamp tolerance.

### Bounded read-only quote buffer — DONE for implementation and bounded XAUUSD acceptance (2026-10-21)

Branch `feature/bounded_quote_buffer`. User explicitly approved causal buffering. Opt-in100ms lead/250ms monotonic residence/64 updates per symbol; pending snapshot inhibition, strict unchanged release validation, generation/reset/overflow/order guards. Default remains unbuffered; execution unchanged and disabled. Decision record `docs/decisions/0003-bounded-shadow-quote-buffer.md`. Installed gateway suite:288 passed+4subtests in6.47s. Actual600s read-only acceptance follows using pinned local-host-009 images and fresh probe-022.

Final buffer regression: **290 passed + 4 subtests in 6.74s**. Fresh probe-022 passed three-sample bid-basis checks for both symbols. Run-019 used both symbols, both workers and pinned local-host-009 images. Host lag measured +130.155ms (Apple) / +128.014ms (Cloudflare), beyond the declared profile. Stopped after44seconds:11 buffered/released updates,75 BUFFER_EXCESSIVE_SKEW rejections, no strict future-release rejection, zero broker writes. Forced reconnect was not reached, so report correctly records INCOMPLETE reconnect. This demonstrates bounds enforcement, not sustained acceptance. All drill containers/networks removed. Evidence: `buffer-guard-shadow-019.json`, `buffer-capability-audit-022.json`. User asked to correct clock locally before repeating; no automatic clock modification or order authorization inferred.

### Buffered shadow acceptance rerun — interrupted; fresh acceptance resumed (2026-10-21)

Branch `feature/buffered_shadow_acceptance`. Operator corrected clock; independent offsets +0.000055 +/-0.009788s (Apple) and +0.001454 +/-0.013179s (Cloudflare). Probe-023 freshly qualified both bid bases. Run-020 uses both symbols/workers,600seconds,forced reconnect at240seconds,unchanged100ms/250ms/64 buffer profile, pinned local-host-009 images. Baseline8e3472d CI39480736712 verified SUCCESS. No runtime source changes or order authorization.

Resume correction (2026-10-21): user reported interruption and requested fresh time-sensitive work. Run-020 gateway finished but core exited during initialization: TPR requires exactly one symbol per instance. The manual dual-universe configuration was invalid; gateway-only PASS is not end-to-end acceptance. Gateway wall timestamps span approximately41minutes rather than planned600seconds, so no sustained timing claim is made. This same manually expanded TPR universe was used in run-019; its zero-decision result cannot be attributed solely to clock skew. Queue guard observations remain valid. Fresh runs will use one symbol per instance and explicit plugin initialization preflight. Initial current host offsets +25.137ms Apple/+25.383ms Cloudflare are within the100ms profile. All prior evidence remains historical.

Fresh EURUSD run-021 initialized both single-symbol plugins successfully. Over approximately415seconds it received70spots, buffered/released56, rejected none and passed forced reconnect. It remained blocked by missing M1 history ending2026-10-20T23:44UTC (329/400 available at final observation); core decisions and all order-side counts remained zero. Stopped once the history blocker was established, not counted as ten-minute acceptance. Probe-025 independently returned no bar and zero bid/ask ticks for23:43–23:44UTC. This is NO_TICKS_REPORTED during scheduled trading, not a certified closure; no candle inserted. Evidence: `restarted-eurusd-shadow-021.json`, `restarted-eurusd-gap-025.json`.

Fresh probe-026 renewed bid basis and independently audited the XAUUSD21:00–22:00UTC daily closure onOct20. Configuration preparation certified the interval against the broker schedule, and both plugins passed explicit initialization. Separate single-symbol run-022 started with600seconds, forced reconnect240seconds and unchanged buffer bounds. Runtime images remain pinned to local-host-009; execution remains disabled.

Run-022 completed in601.816seconds: gateway PASS, reconnect PASS (generations1/3), all400/80/24/16 real bars,1,475spots,1,288buffered and released, peak queue2, no pending/drops/quote rejections. Core440events/880decisions: TPR440WATCH; timer1ENTRY/439NO_ACTION. Shadow entry produced no command; commands/reservations/positions and broker writes allzero. Successful external samples show decision totals30–402 in generation1 and402–880 in generation3. There were52 complete gateway snapshots and58 reconciliations, one recorded collection failure; these counters are not an uninterrupted-availability percentage. Final quote age17.949ms. The ten-minute causal-buffer/reconnect acceptance passes for XAUUSD only; EURUSD, full S5/S6, long-term soak and execution qualification remain open.

External host sampling encountered26 transient read errors during container writes (23malformed-database,3not-a-database); cause is unestablished, and this sampler must not be used as an authoritative continuous availability monitor. Both stopped databases passed full SQLite integrity checks, and final persisted counts were read after core shutdown. All shadow-020/021/022 containers/networks cleaned up; private rotated tokens and reports retained. Sanitized final evidence: `docs/evidence/restarted-xauusd-shadow-022.json`. No runtime source changes; prior installed regression290tests+4subtests and baseline CI remain the implementation validation. Evidence JSON parsing, sensitive-key checks, bounded acceptance assertions and git diff --check passed. Evidence commit0bd2899 and merge6bc47b3 were pushed to origin; no new CI success is claimed.

# Strategy API v1 — proposed contract

Status: design only. Companion to [platform design](autonomous-scalping-agent.md).

## Ownership boundaries

| Strategy package owns | Shared platform owns |
|---|---|
| Instrument universe and required features/history | Provider access, normalization, timestamps and data quality |
| Event subscriptions and decision cadence | Scheduling, resource quotas and immutable event delivery |
| Signal rules, candidate states, entry and exit proposals | Schema validation, ownership and authoritative broker state |
| Parameters, model/prompt versions, strategy-specific constraints | Account risk limits, capital allocation and margin enforcement |
| Desired order semantics, permitted fill envelope and validity | Capability checks, order translation, submission and reconciliation |
| Strategy tests and performance evidence | Contract tests, audit storage, supervision and recovery |

TPR-specific rules—including minimum 2R, TP1, M1/M5 timeframes, three-bar entry expiry and spread-to-stop ratios—belong in the TPR package/profile. No shared module imports TPR code. Packages cannot call the broker, read secrets, write account state or alter risk policies.

## Package and instance

A **package** is an immutable versioned implementation. An **instance** binds that package to parameters, instrument universe, account, operating mode, capital allocation and supported execution/risk profiles. Multiple instances can use the same package without sharing mutable state.

Example binding (illustrative design syntax):

```yaml
instance_id: tpr-eurusd-shadow
package: tpr1@1.0.0
package_digest: required-at-install
contract_version: 1
mode: shadow
account_ref: configured-account-alias
universe: [EURUSD]
parameters_ref: tpr1-baseline-eurusd
execution_profile: tpr-auto@1
risk_profile: linear-stop-risk@1
allocation_ref: account-policy/strategies/tpr
```

The manifest declares:

* Contract version, package ID/version/hash, parameter schema and state schema version.
* Instrument types and universe constraints, including whether decisions require a multi-instrument snapshot.
* Required feeds, price basis, timeframes, warm-up counts, features and freshness/completeness requirements. Non-price inputs include both effective time and actual publication/availability time.
* Subscribed events: finalized bars, ticks, timers, owned order/position events and health events. Timer clock semantics and timezone are explicit.
* Supported decision kinds, required broker capabilities, execution/risk profile compatibility and permitted management actions.
* Evaluation timeout, resource limits, dependency versions and recovery behavior.
* For model-based packages: model artifact or provider/model identifier, prompt/schema versions, input dependencies and reproducibility limitations. External model access goes through a permissioned platform service; the worker receives no provider secrets.

A package requiring unsupported data, risk semantics or order capabilities cannot enter an executable mode. It receives a precise incompatibility result rather than a best-effort substitution.

## Worker interface

The following is an interface sketch, not implemented Python:

```python
class Strategy:
    def manifest(self) -> StrategyManifest: ...
    def initialize(self, context: ReadOnlyContext, parameters: dict) -> State: ...
    def evaluate(self, event: Event, snapshot: Snapshot,
                 portfolio: OwnedPortfolioView, state: State) -> Evaluation: ...
    def validate_proposal(self, proposal: Proposal,
                          snapshot: Snapshot) -> ValidationResult: ...
    def migrate_state(self, prior_version: str, state: State) -> State: ...
```

`Evaluation` contains next state and zero or more decisions. State migration is optional; an unsupported migration requires draining the old instance and initializing a new one. Validation is strategy-specific; it does not replace independent platform validation or account risk checks.

The host supplies time through events, never ambient wall-clock reads in strategy logic. Workers have no filesystem/network side effects; explicit data/model service results are recorded as inputs. Persist the event cursor, next state and decisions in one transaction. Replay preserves event ordering and stable decision IDs. Deterministic packages must reproduce decisions exactly; model-based packages replay recorded model responses and report limits of fresh model reruns.

## Common decision envelope

Every decision carries:

* Instance/account/environment identity; package, parameters, model, execution and risk policy versions.
* Event ID, source and observation timestamps, decision cutoff, snapshot hash and deterministic decision/intent IDs.
* Outcome: `NO_ACTION`, `WATCH`, `PROPOSE_ENTRY`, `PROPOSE_MANAGEMENT`, or `UNAVAILABLE`.
* Evidence references, reason codes and optional namespaced diagnostics. Candidate lifecycle terms such as TPR's `FORMING` remain plugin details.
* For actionable proposals: explicit validity deadline, preconditions and instrument/order ownership references.

An entry proposal specifies instrument/side, order type and prices where applicable, a permitted fill envelope, desired sizing policy or target exposure, protective/exit instructions and execution profile. Different proposal variants have distinct schemas: a market entry does not need a fake trigger price, and a timed exit does not need a fake TP1. A strategy without a TP can use a supported timed/conditional exit profile; the initial live capability still requires a protective stop.

A management proposal specifies the owned order/position and action (`CANCEL`, `CLOSE`, `REDUCE`, or supported protection amendment), expected broker-state revision, reason and deadline. It is revalidated against current broker state before execution. Reducing exposure remains possible when the entry budget is exhausted; exposure-increasing actions require a new reservation. Stale proposals cannot overwrite newer fills or protection changes.

All prices/quantities use decimal representations with units and price basis. Strategy-estimated risk or confidence is informational until independently validated. Optional fields remain absent when inapplicable; the platform does not impose a universal target, reward/risk ratio or probability score.

## Multiple strategies on one account

State keys include account/environment, instance ID, package version and instrument/universe identity. Intent IDs include the instance and decision/action ID, so identical signals from different strategies remain attributable while retries within one instance deduplicate.

The account controller atomically reserves risk across every strategy and pending submission. Allocations are budgets within the account ceiling, not extra risk added above it. A deterministic arbiter orders simultaneous proposals using configured priority, decision time and intent ID. Rejected or deferred proposals retain reasons and cannot execute after expiry.

Initial conflict policy is exclusive symbol ownership: one strategy's pending/open exposure blocks another strategy's entry in that symbol. Never automatically combine opposite signals or cancel another strategy's position. Hedged or netted portfolios require a future allocation ledger, netting-aware P&L attribution and explicit broker capability support. Cross-symbol and shared-factor concentration limits remain account policy.

Multi-instrument analysis is allowed at the interface level. Atomic multi-leg execution is a separate capability; the initial executor rejects executable basket proposals until partial-leg risk and recovery are implemented.

## Loading, replacement and failure

1. Install a package into a registry after schema, dependency, capability and conformance checks. Prose-only strategies first become an explicit specification and adapter; resolve ambiguous rules before executable deployment.
2. Start an instance in shadow mode with an immutable parameter/config hash. The registry constructs workers and data subscriptions from its manifest.
3. Evaluate the package in replay and forward observation, then independently select its permitted operating mode. There is no self-promotion or live self-modification.
4. To replace a strategy, stop new entries, cancel or finish its pending orders, and keep the original instance/version responsible for its existing positions until they close. An explicit compatible migration may transfer ownership; never silently attach old positions to new logic.
5. On a worker crash or timeout, isolate that instance, inhibit its entries and apply its predeclared recovery profile. The shared executor retains broker protection and reconciliation. Sibling instances continue only if account-wide health remains valid.

Package removal is blocked while it owns exposure or unresolved submissions. Broker event ingestion and risk management continue even when analysis is unavailable.

## Proof that the platform is decoupled

Acceptance requires these demonstrations:

1. TPR-1 produces the same baseline analysis results through the generic interface as its existing helper.
2. A synthetic strategy fixture subscribes to H1 and timer events, uses market-entry proposals and a timed exit with protective stop, and has no TP1 or 2R rule. Loading it changes configuration/package files only, with no core-code changes. This is an architectural test, not an investment recommendation.
3. Both instances run concurrently with isolated state, shared data where compatible, account-wide atomic reservations and deterministic conflict handling.
4. Malformed outputs, unavailable evidence, timeouts, unsupported order types and attempts to amend another instance's trades are rejected.
5. Replay and crash recovery preserve decisions, ownership and outstanding risk; model-backed strategies can replay their recorded responses.
6. Replacement during an open trade preserves its original management policy. Unsupported multi-leg/stopless strategies receive explicit capability errors.

Adding strategy N therefore means supplying a conforming package and instance configuration. Adding a new broker, asset class, risk model or execution primitive may still require a platform extension; this limitation is explicit rather than hidden inside strategy logic.

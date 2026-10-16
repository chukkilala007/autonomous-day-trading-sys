# Demo integration boundary and offline evidence

The current mandate is offline implementation/testing only. Default Compose remains paper. `compose.shadow.yaml` remains read-only. No actual broker orders were placed or enabled.

## Delivered path

`runtime.demo_service` loads explicit demo instances and isolated workers, locks its core database, obtains a gateway fence, reads fresh normalized snapshots/contracts, and runs the same strategy, portfolio risk and outbox pipeline as paper. `DemoBroker.tick` never simulates fills. `gateways.ctrader.demo_server` exposes authenticated framed RPC; `reactor_server` marshals controller operations onto the SDK reactor. `DemoAPI` accepts only the bound account/current fence and routes supported entries, owned management and recovery to the existing gateway components.

`Projection` converts owned authoritative order/position records into durable core `BrokerEvent` records. Full order identity and broker position binding are required. An acknowledgement is not management completion. Missing settlement facts keep exposure/risk unresolved and inhibit new entries. Projection IDs/revisions survive restart; no blind resends are added. Partial cancellations do not imply closed positions.

`tests/broker/test_demo_end_to_end.py` sends deterministic protobuf envelopes through actual authenticated TCP, then through the shared executor. It verifies accepted → filled → closed, zero risk release before settlement, no duplicate send, stale fencing, disabled authorization and unknown exposure. Other tests cover lost acknowledgement across core restart, management confirmation, cancellation/fill races and protection recovery. These are offline protocol fixtures, not provider qualification or performance evidence.

## Provider inputs still required before actual deployment

`DemoAPI` receives a `valuation()` callback returning an audited account-bound object with:

- `mode: demo`, exact `account_id`, UTC `observed_at` no older than two seconds, evidence hash and classification (`broker_verified` or `demo_observed`).
- `account`: exact decimal strings for balance, equity and free margin, plus verified three-letter account currency.
- `history_complete`: completeness for the required reconciliation window; `external_exposure` must explicitly be false for new entries. Unknown/external exposure blocks entry allocation.
- `contracts`: instrument-keyed strict `risk.sizing.Contract` records. Currency, tick/volume grid, contract value, conversion, commission/slippage allowance and margin require audited sources. The core-approved contract must still match at send time.
- `settlements`: command-keyed verified net account-currency outcomes, with exact `position_id`, `complete: true` and evidence hash. Completeness must include all opening/closing deals, fees, swaps and conversion costs; a closing price alone is insufficient.

Capability reports are independently account/symbol-bound, expiring and restricted to the initial hedged-account, protected-limit profile. Market/stop variants and netted allocation require separate verified extensions. The timer fixture therefore is not automatically executable on this initial demo profile.

An actual provider exporter must be implemented/qualified against the selected broker's available metadata and economics; this code deliberately has no fabricated valuation or signed-cost fallback. Actual startup must also attach every SDK execution event to the durable ledger, perform cold/reconnect history reconciliation, wire the gateway RPC server on its private network, and confirm graceful shutdown. The reactor server factory and core loop are implemented; an authorized operational gateway bootstrap/configuration is intentionally not enabled under the offline mandate.

Before actual qualification, record the provider evidence and configuration/package hashes, supply an explicit demo-test mandate and use a separate account-bound deployment/state directory. Never change the paper or shadow deployment into a mutating gateway merely to make an offline fixture pass. S5–S7 parent acceptance remains open until actual provider/host evidence exists.

## Validated economics input (F5.2a)

`gateways.ctrader.valuation.export` now provides the provider-independent exporter boundary. Its strict `Valuation` schema validates account/currency, observation and contract freshness, exact decimal amounts, unique settlement allocation, full lifecycle history coverage and equal opened/closed quantities. Settlement net includes every supplied signed account-currency cash movement, including opening fees; duplicated movements, foreign currencies and incomplete costs reject. Original input evidence and the canonical exported record are hashed.

This is a validated input adapter, not a raw cTrader economics mapper. The selected broker exporter still must establish field/sign/conversion semantics and certify complete movements. A truthful zero outcome requires explicit zero-valued evidence. No defaults invent margin, exchange rates, costs or account balances. Invoke `export(serialized_observation, account_id, now)` from the valuation callback; source assertions do not become provider qualification merely by passing schema validation.

## Gateway lifecycle (F6.3b)

`lifecycle.assemble` constructs the SDK-event callback, durable ledger, fresh valuation callback, core RPC controller and private reactor-dispatched server. It returns `RunningGateway` and the controller with **authorization false**. `start()` starts polling/RPC/client; `stop()` first invalidates observations, stops polling, drains RPC off the reactor thread, then stops the SDK. The caller owns the locked database and closes it only after successful shutdown; an outstanding provider collection fails shutdown explicitly rather than closing underneath it. No credential-bearing CLI or enabled deployment is supplied.

The injected provider implements asynchronous `reconcile(reconnect=...)`, returning `account_id`, `history_complete: true`, a serialized strict `valuation.Valuation`, and `execution_events` with original account-bound execution/order/position facts. History must cover the oldest unresolved intent and opening costs; missing positions must never be synthesized as closed. Cold/reconnect calls are distinguished. The lifecycle reconciles unknown order correlations, applies historical facts idempotently and only then publishes the observation. A concurrent execution event or connection-generation change rejects collection. SDK execution events always invalidate valuation and are persisted before another poll can become ready. Errors, stale inputs and shutdown prohibit observations. The selected provider still needs the actual historical facts and economics mapper; passing these offline tests does not authorize orders.

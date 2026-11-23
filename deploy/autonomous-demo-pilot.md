# Autonomous strategy demo pilot

This boundary lets a reviewed strategy decide whether and when to submit one bounded cTrader demo entry. It does not let a strategy change its account, package, configuration, instrument, size, loss ceiling, geometry, validity window or broker/runtime review.

## Safety model

`PilotMandate` is deployment-pinned and demo-only. It binds one account, strategy instance, package/version, full instance configuration hash, instrument, exact quantity, maximum modeled loss, order type, side, stop distance, reward/risk floor, decision age, proposal lifetime and validity window. It also binds the reviewed broker bundle, source and image identifiers.

The gateway reparses the durable core `Decision`; caller-provided readiness flags are not accepted. It requires an `ENTRY` from the exact reviewed strategy and requires the command ID to equal the canonical decision ID. A mismatch, stale decision, unsupported proposal, changed sizing or expired input fails before transport.

After all broker observation, contract, sizing, quote and risk checks pass, the gateway durably consumes `autonomous-pilot-entry:<account>` immediately before the existing UNKNOWN-before-send boundary. A crash or timeout cannot authorize a retry. Management remains limited to correlated owned exposure through the existing recovery path.

The example mandate is deliberately disabled and contains invalid placeholders. Replacing it is review work, not a startup convenience.

## Required activation sequence

1. Select a versioned strategy package that can emit the broker-supported protected limit proposal without core edits.
2. Create a demo `Instance`; independently review its package digest, parameters, account policy and configuration hash.
3. Renew broker account, market coverage, clock, modeled-risk configuration, source and image evidence.
4. Build and independently pin a `ReviewedBundle` for the same account, instrument and exact quantity.
5. Create a unique one-entry `PilotMandate`; run `pilot_preflight.check` and retain the `PREPARED_DISABLED` result.
6. Start the isolated strategy worker, core demo service and broker gateway with separate state and credentials. The broker gateway alone receives cTrader credentials.
7. Enable the gateway only for the exact mandate window. `NO_ACTION`, `WATCH` and `UNAVAILABLE` decisions do not consume the pilot or submit an order.
8. Once an entry is consumed, do not re-arm. Reconcile, protect/close owned exposure, review settlement and archive the completed cycle.

## Current readiness

The authorization boundary and strategy-to-gateway protocol are implemented and tested offline. The current TPR-1 adapter deliberately permits executable proposals only in paper mode and emits `stop_limit`, while the timer strategy is a synthetic market-order fixture. Neither is eligible for this cTrader pilot, whose reviewed broker path currently supports protected limits. Do not relax either strategy or broker capability merely to produce a trade.

Before an online autonomous pilot, implement or review a broker-compatible strategy package, supply its actual demo instance, add the intended-host launcher configuration, and observe a naturally produced eligible decision in shadow mode. No autonomous broker order is authorized by this document or the disabled example.

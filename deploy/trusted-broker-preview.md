# Trusted broker-data binding for the first attended preview

`gateways.ctrader.attended_binding.Binding` connects the read-only preparation function to existing broker components. It has no order method, submission flag, credential loader or enabled launcher.

## Deployment assembly and trust boundary

The trusted composition root constructs `ReadOnlySession`, `Feed` and `Stream` for the same selected account, database and EURUSD symbol ID. Supply a `ReviewedBundle` and its separately approved canonical digest, a previously acquired `Fence` core/epoch, and the UTC clock. Construct Binding before starting the session. It owns the client's message callback: do not install another lifecycle callback afterwards or share this session with another controller. Authenticate and repair the stream before calling `preview(entry)` on the reactor thread.

The caller supplies only an Entry. It cannot supply quotes, balances, readiness booleans, valuation or margin. The existing preview function remains a low-level validator, not a trusted runtime entry point. This is an in-process trust boundary, not isolation against malicious Python code or an administrator modifying storage.

The approved bundle binds account, symbol, complete cost policy, price/protection/expiry reviews, source hash and image digest. Pin the digest in separately reviewed deployment configuration; never take a bundle and its purported trusted digest from the same untrusted request. The hash provides content integrity against the deployment pin, not broker signature verification or proof that a reviewer is correct. No real-account approved bundle is provided because the remaining broker facts are unresolved. Do not copy synthetic test reviews into deployment.

## Collection and rejection

- Authentication records demo identity against its connection generation; disconnect/authentication failure revokes it.
- Symbol-list and symbol metadata reads must match EURUSD, enabled trading, the approved volume grid and the supported zero-distance protection profile.
- EconomicsCollector brackets account balance/reconciliation and uses server P&L and explicit monetary scales. Only a flat USD FxPro hedged account is supported here.
- A correlated expected-margin read requests exactly100000 wire units (=1000 EUR units); the reviewed complete round-trip cost policy supplies costs. USD-to-USD conversion is exactly1; other currencies are rejected.
- Quotes come from the same stream/feed. Invalid, stale, unrepaired, pending-buffer or foreign-generation quotes are rejected. The original source time is preserved.
- The durable fence is checked before/after collection. Any local commands, attempts, positions, reservations, halts or historical broker intents block this first-test adapter. Do not delete history to pass: use a separately designed recovery workflow for a used ledger.
- Reconnects, fence changes, account changes, any non-spot broker event or malformed event invalidate collection. Event invalidation requires fresh assembly/reconciliation; there is no automatic clearing API. Concurrent preview calls are rejected.

The entry expiry stays exactly60seconds after its original proposal creation time (derived as expiry minus60seconds). Collection may consume at most10seconds of that period; quote/account/margin freshness remains at most2seconds and preview validity ends at the earliest input deadline. The adapter never rolls expiry forward. These limits are preparation semantics, not broker acceptance of an expiry duration.

A successful result is PREPARED_NOT_AUTHORIZED with orders_enabled=false. It cannot be used as a send-time permit. Fenced submission/management integration, explicit bounded authorization and fresh send-time checks are still required. Real broker acceptance of this binding remains untested until an actual reviewed bundle exists.

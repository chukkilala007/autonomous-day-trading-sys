# Attended submission and management adapter

`gateways.ctrader.attended_adapter.Adapter` composes the trusted Binding, existing DemoTransport, ExecutionLedger and owned management sender. Disabled by default. There is no enabled launcher, approval issuer or HTTP endpoint in this feature. No demo order was sent during implementation.

## Approval and composition

The trusted composition root supplies an immutable Approval and independently pinned digest. It binds the exact account/test/proposal, reviewed bundle, capability report, approval time, submission deadline,1000-unit size and maximum modeled loss of at mostUSD5. The preview additionally enforces0.1%equity. A request body carrying its own approval hash is not authorization. Deployment and Python composition are trusted; hashes do not authenticate a human's consent.

Both Adapter.enabled and DemoTransport.authorized must be deliberately set by a future authorized launcher. They remain off in actual deployment. The adapter owns the session message callback, forwarding quotes/invalidation to Binding and execution events to the ledger. Do not replace that callback afterwards or share the session with another lifecycle. Binding's read requests still use the read-only allowlist. The separately authorized DemoTransport is the sole explicit write path through the shared SDK client; merely constructing or calling Binding cannot submit.

## Entry path

Submission refreshes the bound preview for the exact approved Entry; validates approval, evidence pins, freshness, quantity and loss; then invokes the existing capability/fence/quote checks. Original account and quote times are retained. The account-wide attempt checkpoint commits before invoking the transport, which separately persists its existing UNKNOWN gateway-send record before sending. A timeout, rejection, disconnect, restart or crash between those records never authorizes a resend. A different test ID cannot evade account-wide consumption. Subsequent tests require a separately reviewed lifecycle, not deleting checkpoints.

A received SDK response returns AWAITING_RECONCILIATION. It is not a fill or settled result. No reservations are released by this adapter.

## Cleanup path

Only cancel and close are exposed. Management requires the consumed approval, current demo authentication/fence, fresh bracketed broker reconciliation, exact ledger revision/record agreement and ownership. Targets must also trace to the original submitted order/position; matching the owner name alone is insufficient. Quantity must remain within1000units. Deterministic action IDs and the existing durable management journal prevent blind duplicate cleanup sends. Acknowledgement returns CLEANUP_UNCONFIRMED, never flat/settled.

The entry approval deadline applies only to entry. Its explicitly scoped owned cleanup remains available after entry expiry, while authentication/fencing/ownership checks remain mandatory. An uncertain cleanup send requires reconciliation, not another command ID. The adapter does not implement the20second/120second scheduler, automatic completion, settlement qualification or a recovery launcher; those must use actual reconciled lifecycle evidence.

## Remaining activation boundary

Production DemoTransport capability checks are unchanged. The adapter deliberately does not relabel preparation documents as actual demo evidence. Missing broker qualification still blocks submission, even with an Approval. A narrower first-test qualification path, if needed to collect first-fill evidence, requires its own implementation and review under decision0004. This feature implements transport orchestration; it does not resolve that evidence-stage distinction or authorize actual trading.

## Timed monitor integration

`attended_monitor.Monitor(adapter, provider, now=clock, enabled=False)` binds the actual Provider to the adapter/session/database and monitors only an existing durable attempt. `tick()` reconciles, projects broker history, checkpoints evidenced settlements and schedules owned cleanup. `start(clock)` optionally runs a one-second Twisted loop. It never calls submit, and a restart never creates another entry. Unknown acknowledgement and cleanup outcomes remain pending. Provider failures inhibit actions; review a clock halt or contradictory completed exposure manually. An unfilled terminal order is explicitly marked TERMINAL_UNFILLED_COST_REVIEW_REQUIRED until cancellation-cost conventions are resolved. Loop stop is not flattening; shutdown with exposure must retain an attended operator/recovery path.

## First-test qualification follow-up

The separate [FirstTestTransport](first-demo-qualification.md) now implements the narrow evidence-stage path described above. It can be composed with this Adapter/Monitor after reviewed pre-trade facts and actual bounded authorization exist. Production DemoTransport remains unchanged; no actual approval or activation is supplied.

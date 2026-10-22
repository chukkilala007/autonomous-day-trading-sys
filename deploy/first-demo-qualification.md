# First-demo qualification path (disabled)

This path implements decision0004 without changing production DemoTransport or CapabilityReport. It is solely for the one approved EURUSD1000-unit protected BUY LIMIT/GTD test. It does not qualify autonomous execution.

## What must already be known

The deployment-pinned ReviewedBundle remains mandatory: complete conservative round-trip costs, account-bound tick/volume grid, protection semantics and entry/expiry restrictions. Missing or unreviewed facts are not supplied by protocol support. No real-account bundle has been created while those inputs remain missing.

`first_test.Review` binds the account, reviewed bundle digest, installed SDK protocol-profile digest and validity window. It declares acceptance_observed=false and is intentionally not a CapabilityReport. Separately pinned Approval still binds the exact proposal and this review digest, one entry, maximum loss, quantity and submission deadline. An approval hash supplied alongside untrusted inputs is not independent authorization.

## Transport assembly

The trusted composition root constructs Binding and Review, then FirstTestTransport(binding, review, approved_review_hash=..., approved_approval_hash=..., authorized=False). Use that transport with the existing attended Adapter, ExecutionLedger and Monitor. Both transport and adapter remain disabled by default. There is no launcher or generated real-account approval in this implementation.

Binding retains a private serialized record only after successful collection; each new preview attempt first clears it. The first-test transport checks the retained preview's proposal, connection/event/fence state, validity, reviewed bundle and loss/quantity bounds. It reads the current quote and checks the original account timestamp. It requires the broker's UTC schedule/holiday metadata to show scheduled-open through the next120seconds; unsupported or closed schedules block. Scheduled-open is pre-trade support, not a promise of acceptance or fills.

No caller-provided preview object substitutes for that internal record. The protocol mapping must match the installed SDK. Price/volume alignment is rechecked against the reviewed policy. Sending also requires the account-wide consumed Approval record to match this exact command/owner and approved digest. The inherited transport persists UNKNOWN before any SDK send; all adapter/monitor no-resend and owned cleanup rules remain.

## Results still to obtain

Broker acceptance/rejection, expiry, returned protection, fills, actual fees and complete settlement are observations produced by the test. The first-test review does not populate or promote these fields. A cancellation without a fill cannot establish fill/fee behavior; Monitor leaves its terminal no-fill result pending cost review. Production activation still uses the unchanged complete capability/qualification gates.

Implementation tests are deterministic and offline. Actual launch still requires reviewed broker facts, fresh preview and explicit human authorization of the bounded order. No orders have been sent by this feature.

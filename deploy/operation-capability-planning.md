# Attended operation capability planning

F6.4j adds explicit planning for the currently implemented demo USD-linear protected BUY LIMIT profile. It does not generalize cross-currency valuation, nonzero protection distances, account types or order types. Those require separately implemented and tested profiles.

A BrokerProfile must provide current reviewed operation evidence for:

- `BUY_LIMIT_ABSOLUTE_SLTP_GTD_60S`: the combined entry operation with attached absolute stop/target and the controller's sixty-second planned expiry. Independent LIMIT, protection and expiry flags do not establish this combined behavior.
- `CANCEL_PENDING`: support for requesting cancellation of an owned pending order, not a guarantee against a fill race.
- `CLOSE_POSITION`: support for requesting closure of an owned position, not a guaranteed execution price or completion time.

Evidence must scope these claims to the selected account, symbol and the reviewed attended constraints. Broker documentation/review can support first-test preparation; actual acceptance remains a later test result. Protocol-only and synthetic evidence cannot qualify a capability. Never invent a reviewed operation claim merely to make a preview succeed.

`operation_plan.plan` checks a pinned profile and identity, preserves the exact proposal, and returns per-operation supported/unsupported/unknown states. Reasons distinguish missing, noncurrent, unqualified and explicitly unknown evidence from broker unsupported. An all-supported result is SUPPORTED_NOT_AUTHORIZED. There is no fallback or enabling switch. Profile and supporting evidence expiry cap the plan's validity.

Offline launch preflight includes this report for profile-backed bundles using configured identity; it does not authenticate a broker. The trusted binding repeats planning against correlated authenticated identity before issuing a preview, and evidence expiry caps that preview lease. Existing first-test transport rejects an expired lease. All pre-existing quote, margin, geometry, schedule, risk, ownership and authorization checks remain.

Legacy bundles without BrokerProfile retain their prior independently pinned review path and restrictions; they are not automatically capability-qualified or migrated. New broker profiles without operation evidence now block. Pin changes require renewed independent review. No existing real-account evidence or orders were enabled.

Capability requirements here are entry prerequisites. They are not a new blanket gate on recovery of already-owned exposure: existing management/reconciliation paths retain their own ownership and current broker-state checks. Unknown entry capability must not be interpreted as permission to abandon an existing position.

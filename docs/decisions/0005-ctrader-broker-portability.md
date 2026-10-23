# cTrader broker portability

Status: accepted architectural direction, 2026-10-23. Implementation migration pending.

The product targets brokers using cTrader. FxPro is the first qualification environment, not the product specification. Supporting a broker means qualifying its account, instruments and execution capabilities; it does not mean every cTrader account supports every strategy or order type. No broker inherits another broker's evidence or execution authorization.

## Boundaries

| Layer | Responsibility |
|---|---|
| Shared strategy/core | Broker-independent analysis and trade intent, portfolio risk, ownership, durable state and reconciliation. No broker names or symbol aliases in strategy logic. |
| cTrader adapter | Authentication, protocol encoding, normalized units/events, reconnect and account-scoped symbol discovery. Protocol support alone is not broker acceptance. |
| Broker/account profile | Verified broker identity, environment, account identifier/currency/type, canonical-to-native symbol mapping, contract geometry, fees, session rules, order/protection/expiry constraints and evidence references. |
| Capability resolver | Decide whether the requested operation is supported, unsupported or unknown using current evidence scoped to broker/account/instrument/operation. Return explicit blockers or a reviewed alternative. |
| Risk policy | Distinguish documented fees, observed fills and modeled adverse-execution assumptions. Model assumptions are never relabeled broker facts. Apply independently of broker identity. |
| Deployment | Supply the selected profile, credentials and independent evidence/approval pins to the same Docker services. Isolate ledgers, writer fences and one-attempt limits per account. |

Profile selection must be verified against authenticated identity, not trusted from a user-supplied broker label. Symbol IDs are account/broker scoped; NAS100, #USNDAQ100 and another broker's alias are not automatically interchangeable contracts. Record source, scope, observation/expiry times and confidence classification for each material fact. Unknown facts block the dependent operation, not unrelated read-only analysis.

## Migration inventory and stages

1. **F5.2r — versioned broker/account profile.** Define immutable identity and symbol mapping, evidence scope and capability states. Preserve an explicit FxPro fixture/profile. Tests: two synthetic broker profiles, same symbol alias with different contracts, wrong identity/environment and expired evidence rejection.
2. **F5.2s — portable capture and trusted binding.** Replace hard-coded FxPro checks in attended_binding.py, algo_capture.py and ContractSpecExporter.cs with independently pinned expected identity/profile checks. Scope symbol/currency support explicitly; do not merely remove guards. Preserve legacy capture parsing and historical provenance. Test mismatched account/broker/symbol, reconnect changes and old/new pin separation. New exporter artifacts require their own build/capture qualification.
3. **F5.2t — broker evidence providers.** Isolate specifications.py's FxPro public-source reconciliation as one provider. Generic discovery and normalized contracts must not depend on FxPro pages. A second broker can use authenticated metadata, local exporter observations and reviewed documentation without scraping the same website structure. Test provider isolation and prevention of cross-broker evidence reuse.
4. **F6.4j — capability-driven operation planning.** Resolve exact entry/protection/expiry requirements against the selected profile. Unsupported and unknown capabilities produce different diagnostics. Generalize current USD-linear/zero-distance attended constraints only through tested profiles; cross-currency valuation is a separately evidenced path. Preserve existing disabled defaults and production gates.
5. **F6.4k — separate risk semantics.** Design a demo modeled-risk path separately from guaranteed/verified bounds. Explicit slippage assumptions, modeled-loss labels and independent approval must propagate through preview, sizing and transport. This is a risk-policy decision common to brokers, not an FxPro exception. Current complete-bound policy stays active until an approved migration is implemented.
6. **Second-broker acceptance.** Run discovery, capture, contract/fee review, read-only preview and reconnect/shadow checks using a separately authorized account. Offline fixtures demonstrate portability of code, not real broker qualification. Actual orders require that account's own bounded authorization.

Each stage follows feature branch from develop, targeted/full checks appropriate to the change, tracker update, commit and no-fast-forward merge. This decision does not claim these stages are implemented.

## Candidate workarounds for capability gaps

| Gap | Candidate to assess | Boundary |
|---|---|---|
| Different symbol names/units | Account-discovered mapping and normalized contract values | Never match by name alone or reuse another account's symbol ID. |
| Missing API TickSize/value | Approved local Algo capture plus account-specific documentation | Preserve freshness/provenance; do not infer tick size from display digits. |
| No GTD or differing minimum expiry | Reviewed GTC plus supervised cancellation, or another supported order profile | Local cancellation is unavailable during outages and cannot replace a hard server expiry requirement. Requires different approval and lifecycle tests. |
| No attached protection for requested order | Select another supported protected order type/account; otherwise reject | Post-fill stop placement leaves an exposure interval and is not equivalent to atomic protection. Do not silently substitute it. |
| Nonzero minimum distances | Recompute valid geometry and resize within strategy/risk constraints | Reject if minimum volume or strategy invalidation makes the result unacceptable. |
| No guaranteed stop execution | Explicit modeled-risk policy, or a separately qualified guaranteed-protection profile if available | A limit entry, stop-limit nonfill, alternate symbol or local stop does not guarantee bounded exit loss. |
| Incomplete fees/adjustment rules | Gather scoped evidence; restrict sessions only where verified rules justify it | Planned early cleanup does not prove absence of overnight/adjustment costs after a failure. |

Workarounds are design candidates, not enabled fallbacks. Capability negotiation must never silently change a strategy's execution semantics. Existing FxPro evidence remains valuable but scoped; the NAS100 review is one broker/account case study.

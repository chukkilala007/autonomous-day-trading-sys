# Configurable cTrader broker dependencies

The product does not require an FxPro support response before preparing a bounded demo trial. Broker documentation is useful evidence, not a universal prerequisite. This supersedes earlier J03–J06 statements that made all account-specific written confirmations mandatory. The new path is explicit operator configuration, available only with the separate modeled demo policy and portable broker profile. No real orders are authorized by this change.

## Source and fallback policy

| Input | Preferred source | Explicit fallback / boundary |
|---|---|---|
| Broker/account/environment, currency, symbol mapping and executable volume geometry | Authenticated feed plus pinned profile | No identity or unit guessing. Feed mismatch blocks; changing broker requires its own profile |
| Tick/grid applicability and USD-linear point value | Captured metadata/Algo or broker documentation | Configure numeric fields in profile/policy and document assumptions; public marketing-label discrepancies need not block if captured units are explicitly chosen |
| Entry/protection/GTD/cancel/close availability | Broker evidence or actual observations | Declare exact operations as bounded demo trials; capability remains unknown until evidence exists |
| Fees, financing, dividends, rounding effects and adverse exit | Broker data when available | Explicit fee/model allowance values and rationale in DemoRiskPolicy/configuration; not guaranteed bounds or universal broker defaults |
| Settlement sign/incidence/completeness | Observed deal/cash records plus reviewed policy | DeferredCostPolicy keeps settlement unresolved; never assume complete cash accounting |
| Fresh quote, current account/margin, ownership/fence and original proposal expiry | Current correlated runtime data | No configurable waiver |

Known broker-unsupported operations cannot be overridden by a trial declaration, including expired negative evidence. Re-review/remove obsolete evidence explicitly with a new profile pin rather than silently ignoring it. Alternative order types/protection or cross-currency/nonlinear contracts require implemented profiles, not configuration pretending support. Current attended runtime remains USD-linear/HEDGED with its existing distance/schedule restrictions; this change does not claim every cTrader account type is supported.

## Configuration

Add `demo_configuration` to ReviewedBundle, using [the deliberately expired example](../config/brokers/operator-demo.example.json) as its shape. Replace example identity/symbol/review fields and explicitly review dates and all seven rationale fields. The file alone is not an executable bundle or approval. Numeric tick/value/quantity/fees/allowances continue to reside in the existing BrokerProfile and DemoRiskPolicy fields, so existing arithmetic and geometry checks remain authoritative. There is no automatic copying of one broker's facts to another.

The configuration is scoped to the exact broker/account/demo environment/instrument/symbol ID, has a finite validity interval and is part of the independently pinned bundle. Model risk must remain `demo_modeled_risk`; attaching this fallback to a complete-bound production policy rejects. Missing operation evidence remains `state=unknown`, with `preparation_basis=operator_configured_demo_trial` and `DEMO_TRIAL_NOT_AUTHORIZED`. Preview output exposes the assumption texts and configuration hash. The legacy verified path retains its checks.

BrokerProfile evidence may be empty for declared trial operations. Do not create fake `broker_verified` rows. Review hashes may identify operator configuration reviews on this path; they do not imply broker endorsement. Explicit feed contradictions, unsupported contracts, unreviewed identity, stale data, expired configuration and excessive modeled risk still block.

Approval must independently acknowledge `accepts_unverified_broker_settings=true`, in addition to modeled risk and unbounded realized loss. The first-test transport still requires the exact reviewed bundle/proposal, fresh send-time checks and a single durable attempt. A rejected or ambiguous order does not grant a retry. Broker acceptance cannot be learned by sending orders without explicit J09 authorization.

## Unknown settlement conventions

The attended launcher's `--cost-policy` accepts either the existing audited CostPolicy or:

```json
{
  "account_id": "REPLACE_WITH_DEMO_ACCOUNT",
  "classification": "settlement_review_pending",
  "review_hash": "REPLACE_WITH_REVIEW_SHA256",
  "verified_at": "REPLACE_WITH_CONFIGURATION_REVIEW_TIME",
  "valid_until": "REPLACE_WITH_REVIEW_EXPIRY",
  "all_costs_covered": false
}
```

Here `verified_at` is the configuration-review timestamp retained by the launcher interface, not verified broker fee knowledge. The policy requires a separate canonical pin and the explicit demo-configuration path. Owned exposure management remains active. If settlement becomes necessary while conventions remain deferred, the monitor returns `SETTLEMENT_REVIEW_REQUIRED`; the launcher stops with `exposure_resolved=false`. It does not fabricate P&L, release accounting state or mark the test COMPLETE. Preserve the database and observed broker records for subsequent review/recovery. Deferred settlement cannot certify production settlement.

## Close-out sequence

J03–J05 no longer require waiting for FxPro replies for this bounded modeled demo route. Select and document configured values/assumptions, assemble J06 and review its independent pins; then collect a fresh J07 preview and obtain explicit J09 order authorization. Prior October market evidence is historical and cannot satisfy November freshness. Broker questions remain optional and unsent. Production/live qualification and actual acceptance remain separate jobs.

Schema additions change canonical bundle and approval hashes, including defaults. Regenerate and independently review pins; do not migrate old approvals automatically. The example contains no real risk amounts or approval. Existing production contracts and verified capability evaluation remain unchanged.

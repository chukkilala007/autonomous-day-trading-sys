# Actual demo settlement and recovery — 2026-11-20

Outcome: test053 now has a verified lifecycle settlement, closed position, resolved cleanup target and COMPLETE monitor state. Connected installed-runtime recovery060 and restart061 both completed with exposure_resolved=true. Exactly one entry record and one cleanup record remain; no new entry or duplicate close occurred. [Manifest](demo-settlement-recovery-060.json).

## Settlement review

Read-only history057/058 contains two deals and three orders (entry, attached protection and close). History058 starts at pre-test probe050, includes all returned deal rows, and contains no deposits/withdrawals. Both deal commissions and closing commission/swap/conversion fields are explicitly zero. Gross resultUSD0.45 matches balance changeUSD10000 toUSD10000.45 and closing-deal balance. Flat reconciliation was recollected.

New ObservedZeroCostPolicy is scoped to exact account, command, position, entry order, quantity, currency, deal hash, baseline and post balances, history window and finite validity. Provider rechecks full window cash/history and flatness before settlement. Nonzero/missing cost fields, extra/changed deals, cash flows, foreign scope or unexplained balance reject. It does not establish general fee signs, incidence, future zero costs or a guaranteed lifetime cost bound. Attended launcher permits it only for recovery. Original proposal/approval/bundle pins are preserved; the separately reviewed recovery deployment records changed runtime source/image and scoped cost pin. This does not authorize reuse of the entry approval.

Protocol reference: [cTrader model messages](https://help.ctrader.com/open-api/model-messages/) defines close-deal monetary scaling and account balance; [cash history request](https://help.ctrader.com/open-api/messages/#protooacashflowhistorylistreq) documents deposit/withdrawal history. These protocol definitions alone do not certify broker fee conventions.

## Confirmed defects and fixes

1. The actual terminal position event reported CREATED/zero volume at the same revision as the final deal. The ledger previously discarded the provider's complete-history CLOSED observation at that equal revision. Narrow promotion now requires zero volume, matched owned original order and settlement evidence. Ordinary raw equal-revision events still cannot promote closure.
2. Cleanup requests were durably UNKNOWN with no outcome reconciliation path. A fully settled owned closure now records TARGET_RESOLVED with evidence hash. This proves the target is closed; request_acceptance_confirmed remains false because flatness alone cannot prove which request caused it. It does not resend or remove the consumed intent.
3. Monitor exceptions previously retained no diagnostic reason. Fixed-code phase/time/failure-count diagnostics now survive successful recovery without recording exception text or private broker payloads.

The original transient RECONCILIATION_REQUIRED cause cannot be proven retrospectively because its reason was discarded. Saved state later returned to MONITORING before intervention. Concurrent broker changes and valuation freshness are known fail-closed paths, covered by tests, but neither is asserted as the historical cause. No evidence justifies claiming fully autonomous original cleanup. Future runtime failures will have usable safe diagnostic codes.

## Validation and limits

Targeted54tests passed; final full Docker suite614tests+4subtests passed in9.33s,11known SDK/Hypothesis warnings. Rebuilt installed recovery image source hash matched local source; live recovery060 and restart061 returned COMPLETE. Durable state assertions verify one settlement, one entry, one cleanup, closed zero-volume position and COMPLETE monitor. Runtime code has no broker-specific hardcoded account/value changes.

User has authorized necessary bounded tests on this demo account; this persists beyond the original one-entry approval. No live-account authorization is implied. Runtime order activation remains explicit per test, and settled records are retained. Further scenario tests must use a reviewed lifecycle workflow, never clear the ledger to bypass one-attempt protection. Cancellation/expiry, nonzero-cost accounting and uninterrupted autonomous cleanup remain separate acceptance scenarios.

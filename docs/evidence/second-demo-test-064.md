# Second end-to-end demo test — 2026-11-20

Outcome: COMPLETE, broker flat, automatic cleanup without manual close. Account10655835/API49644649. [Manifest](second-demo-test-064.json).

## Actual lifecycle

Fresh baseline062: USD10000.45, USD/HEDGED, NAS100/native#USNDAQ100/1107. New bundle063 pins refreshed account-scoped modeled policy and tested runtime; quantity0.01, fixedfee0.25, adverse50points, othercost0.50 unchanged. User requested another end-to-end test under standing bounded demo authorization.

One fresh BUY LIMIT064: limit25268.25, stop25168.25, target25368.25, original60second GTD. Broker order251110637 filled at25266.60; position155928858 observed protected. Monitor recovered from transient failures and automatically requested owned closure after its120second attempt deadline. Close order251110699 filled at25333.25. No manual close, entry retry or changed expiry. Execution runner stopped with SETTLEMENT_REVIEW_REQUIRED as designed.

History065 confirmed two deals, no deposits/withdrawals, explicit zero reported costs and no open positions/pending orders. Scoped review066 reconciled USD0.67 to balanceUSD10001.12. Recovery067 with installed final runtime returned COMPLETE; ledger position closed, cleanup TARGET_RESOLVED. Settlement review remains a separate post-run step, not automatic universal broker-cost qualification.

## Sequential test support

The original one-attempt gate was account-wide. New advance_completed_test requires fresh correlated broker-flat economics, prior COMPLETE monitor and matching approval, exact original send, validated complete settlement, owned closed position, terminal related orders and resolved cleanup. Unrelated halts, core state, foreign/ambiguous records or stale evidence reject.

In one transaction it preserves prior checkpoints and resolved protection halts in a hashed completed-test archive, writes permanent consumed-approval/test-ID records, invalidates the previous writer fence, and declares the explicit next test ID. Only then are archived projections removed from active queries. The same database is retained; history is not discarded and no blank replacement ledger is created. Adapter construction and every write check reject historical approvals and a mismatched active cycle, including previously constructed adapters. Tests cover rejection rollback and replay prevention.

## Runtime findings and validation

Monitor recorded7failed reconciliation ticks, then recovered. Last classified failure: BROKER_CHANGED_DURING_RECONCILIATION, consistent with actual execution updates changing state during collection. Earlier generic provider failures are not retrospectively assigned the same cause. These failures did not trigger duplicate orders or prevent automatic closure.

A filled protected position was incorrectly labelled EXPIRY_UNCONFIRMED after60seconds. Corrected that label to require a pending quantity; no execution deadline or risk control changed. Sixteen targeted monitor tests passed after the correction. Full suite before that label-only change:625tests+4subtests in11.18s,11known warnings. Initial transition/adapter/launcher subset42passed. Final runtime rebuilt and installed source hash verified against local source; actual recovery067 passed. Entry runtime and final recovery runtime are separately pinned because of the label correction.

Remaining scenario acceptance: cancelled/unfilled expiry path, nonzero costs, interrupted connection during active exposure and longer unattended operation. This successful test does not establish those scenarios or strategy profitability. Standing demo testing authorization persists; no live-account permission.

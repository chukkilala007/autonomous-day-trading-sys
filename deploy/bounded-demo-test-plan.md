# Proposed first attended demo-order test

Status: PREPARED, NOT AUTHORIZED FOR SUBMISSION. User requested preparation on 2026-10-20. This document is not executable configuration and does not enable the gateway.

## Scope and hard bounds

- Account: selected cTrader demo account 48232468, confirmed `isLive=false` immediately before testing.
- Host: this Mac, Docker Desktop; one fenced gateway writer and one attended test controller.
- Instrument: EURUSD only. Exclude XAUUSD until its volume-step discrepancy is resolved.
- Initial test: one BUY LIMIT submission, 1,000 EUR units (the previously observed minimum), with attached absolute stop and target and GTD expiry 60 seconds after submission.
- Maximum one order attempt, one pending order or owned position, and 1,000 EUR gross quantity. No second submission after rejection, timeout, reconnect or ambiguous acknowledgement.
- Proposed planned-loss ceiling: USD 5 including verified fees and modeled exit costs, additionally capped at 0.1% of freshly reconciled equity. Reject if the minimum size cannot fit both limits. This is a pre-trade bound, not a guarantee against gaps or slippage.
- Prices are not chosen from stale data. Immediately before the attended test, produce a timestamped preview with grid-aligned entry, stop, target, current bid/ask, spread, fees, margin, expiry and worst modeled loss. All must pass the existing validators. A valid proposal may be unavailable; do not widen limits to force a test.
- No autonomous strategy entries. This tests transport/lifecycle, not TPR performance or its stop-limit semantics.

## Preconditions

1. Obtain exact account tick, contract/economics, protection-side and limit/GTD capability evidence. Where execution behavior requires observation, record protocol/broker support separately from actual demo acceptance. Do not fabricate `demo_observed` evidence to pass the capability gate. If the current gate cannot represent that distinction, implement and test a narrowly scoped qualification path first.
2. Resolve host/guest/broker timestamp alignment and demonstrate a 10-minute read-only interval including one forced reconnect, complete required histories and post-repair fresh quotes, with zero future-quote rejections. Normal missing/stale updates must inhibit decisions. This is a proposed prospective acceptance criterion, not a claim about previous runs.
3. Confirm no unknown outstanding commands and reconcile all broker exposure. Never cancel, amend or close unrelated orders or positions. Abort if existing exposure prevents the test limits from being established.
4. Pin tested images, exact source and policy hashes. Validate current account/quote freshness and proposal-specific economics at send time.
5. Prepare durable event capture, owned cancel/close/protection recovery and an operator monitoring window. Verify the disabled assembly offline using the exact proposed limits.
6. Present the final timestamped preview and obtain explicit authorization for that bounded submission. Preparation authorization alone does not override the earlier orders-disabled instruction.

## Sequence and outcomes

1. Submit once through the durable outbox and fenced transport; capture intent hash and broker correlation.
2. If accepted and still pending at 20 seconds, request one owned cancellation. Confirm terminal cancellation or server expiry through reconciliation; a cancellation request is not terminal evidence.
3. If filled at any time, confirm all filled quantity has the specified broker protection. Halt new entries. Apply the tested owned protection-repair/close policy if protection is absent; reconcile actual outcome.
4. Close any remaining test-owned position by 120 seconds when connectivity permits. Record inability to close honestly and retain halt/uncertainty until broker evidence resolves it. Never report a local timeout as flat.
5. Reconcile deals, fees, cash settlement, remaining quantity and reservations. Finish only with verified zero test-owned exposure and no unresolved command, or an explicit failed/halted incident record.
6. Stop the controller. No unattended retry or promotion to autonomous execution.

A nonfilled cancellation test does not qualify fill economics or protection. A filled test does not qualify cancellation races, partial fills or ambiguous-send recovery. Subsequent separately bounded cases must cover those paths, using deterministic transport fault tests where a broker event cannot safely or reliably be induced. Record actual versus simulated evidence separately.

## Later qualification cases

After the first result is reviewed: expiry without manual cancellation; protected fill/owned exit; partial-fill handling when observed; cancellation/fill race; reconnect and process restart with owned exposure; accepted-but-unacknowledged recovery without duplicate submission; controls/dashboard/alerts; isolated backup restore and broker reconciliation; representative host soak and graceful upgrade. Each needs its own explicit limits and acceptance record.

Remaining blockers and current evidence: [online validation matrix](../docs/evidence/online-validation-2026-10-20.md).

## Read-only preparation update — 2026-10-21

EURUSD run025 completed the ten-minute full-history/reconnect check with zero quote rejections and530shadow decisions; ordinary stale quotes remained blocked. No quote needed causal holding in that run; XAUUSD022 separately exercised actual buffer releases. These historical bounded checks do not replace fresh send-time data or a host soak.

Execution review030 verifies installed LIMIT/GTD/absolute-protection protobuf encoding and explicit account metadata (HEDGED, FULL_ACCESS, not limited-risk; EURUSD ENABLED). It does not qualify attached protection triggers, executable tick size, full economics or actual order acceptance. Limited-risk accounts require a different protection profile. See the [unsent broker evidence request](broker-execution-evidence-request.md). No order authorization or submission has occurred.

## Disabled controller delivery — 2026-10-21

`execution.bounded_demo.Controller` implements durable offline rehearsal of one submission,20second cancellation,60second expiry observation, immediate unprotected-position closure and120second owned cleanup. It never writes executable commands or connects to a broker. State survives restart; expiry/cancel/close requests do not establish flat or release settlement. Tests include partial fill, stale/disconnected/foreign observations, clock rollback, plan replacement and contradictory post-completion exposure.

The real attended adapter/qualification gate is still required. See [evidence-stage decision](../docs/decisions/0004-bounded-demo-evidence-stages.md). This separates pre-trade documentation/policy facts from observations the first test must produce, without weakening production DemoTransport.

## Read-only preview boundary — 2026-10-22

`execution.attended_preview.prepare(entry, quote, valuation, preconditions, now)` accepts strict typed inputs and returns a hash-bound expiring preparation report. It calculates exactly1000units using proposal-bound complete cost/margin evidence and the stated loss ceilings, plus a conservative10%equity margin reserve. Missing mandatory reviews/reconciliation/fencing yield BLOCKED; passing checks yield PREPARED_NOT_AUTHORIZED. Preview lifetime is at most the remaining two-second freshness window. Human approval of a historical preview cannot authorize changed prices or a rolled expiry: a future adapter needs explicit bounded authorization semantics and fresh send-time revalidation.

The function has no broker client, database writes or submission switch. Input hashes and boolean claims require trusted provider binding before an attended adapter can use them. No executable adapter or live preview is claimed. Account TickSize0.00001 was actually captured; pending-entry/protection grid applicability and the remaining broker facts are still separate.

## Trusted binding implementation — 2026-10-22

The read-only preview now has a [trusted broker-data binding](trusted-broker-preview.md), independently deriving dynamic inputs from the account-bound session/feed, bracketed economics, margin response and local fence/ledger. It requires a separately approved review-bundle digest. No real-account bundle is supplied while broker facts remain missing. Submission/management adapter and bounded authorization remain outstanding; a successful bound preview still cannot submit.

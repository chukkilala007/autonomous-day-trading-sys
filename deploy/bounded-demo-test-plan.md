# Proposed first attended demo-order test

## Current J09/J10 disposition — 2026-10-24

Status: DRAFT WITH BLOCKERS, NOT AUTHORIZED. This section supersedes the historical EURUSD scope below. The current candidate is NAS100 / #USNDAQ100 /1107 on selected demo account48232468, minimum0.01units, on this Mac's Docker host. J08's [attended launcher](attended-test-launcher.md) is implemented and offline-tested; no actual order has been sent.

Proposed test: one protected BUY LIMIT with absolute SL/TP, original proposal expiry60seconds after proposal creation (not after delayed submission), one durable account-wide attempt, exact minimum quantity. Modeled budget is the smaller of USD5 and0.1%fresh equity, with10%equity margin reserve. Realized loss is not bounded. No second attempt after uncertainty/rejection/restart; no strategy trading. These are proposed authorization limits, not an approved order.

| Final authorization input | Current state |
|---|---|
| Selected account and native symbol | Historical authenticated/exporter evidence; revalidate at run |
| Account grid, cost and operation applicability | J03–J05 unresolved |
| Independently pinned executable policy/profile/bundle | J06 blocked; review packet is non-executable |
| Reviewed adverse-exit/other-cost amounts and settlement conventions | Missing; never infer zero or a guaranteed bound |
| Exact entry, stop, target, expiry and original proposal hash | Not selected; need fresh market conditions |
| Timestamped connected preview and current clock/feed qualification | J07 blocked; historical EURUSD interval does not qualify NAS100 |
| Tested deployment | J08 installed suite578tests+4subtests; gateway disabled smoke passed; final independent release pins still J06 |
| FirstTest Review, Approval, four independent launcher pins | Not issued; needs complete reviewable configuration and explicit authorization |

After evidence is available, run the required read-only interval/reconnect checks for the selected symbol and a fresh connected preview. Present the exact proposal and modeled assumptions for authorization; subsequent send-time collection must still validate the unchanged proposal before its original deadline. If approval arrives too late, do not renew expiry or change prices under that approval. Generate a new reviewable proposal and obtain fresh authorization. No approval question is being asked now because prices, assumptions and the executable bundle are missing.

J10 acceptance records must distinguish accepted/rejected/unfilled/filled/uncertain outcomes, original correlation, actual attached protection, owned cleanup, reconciliation and settlement. The monitor requests cancellation after20seconds or partial fill, closes unprotected owned exposure promptly and requests residual closure at120seconds. The launcher stops unconfirmed after180seconds if necessary; that is not a flatness guarantee. Preserve state for recovery/operator takeover. No-fill is not fee or protection qualification. Further lifecycle cases remain separately scoped after first-result review.

J09 remains BLOCKED (draft prepared, authorization absent). J10 remains BLOCKED and unattempted. This pair cannot be completed by offline tests or by reclassifying general broker documentation. Next unblock actions are J03–J06 evidence/assumptions and J07 fresh qualification.

## Historical plan and delivery record (superseded where above differs)


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

## Submission/management adapter — 2026-10-22

The [disabled attended adapter](attended-adapter.md) now implements pinned approval, fresh bound preview, account-wide one-attempt consumption and owned cancel/close dispatch through existing durable transports. It preserves full production capability requirements. This does not yet resolve the first-test evidence path or integrate timed monitoring/recovery; no submission authorization or real orders.

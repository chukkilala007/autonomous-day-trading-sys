# Cancellation, expiry and reconnect review — 2026-11-21

Intended cancellation test070 was submitted November20, before the chat interruption. The order expired unfilled; no cancel request was sent. Do not mark automatic cancellation as passed. [Manifest](cancel-expiry-reconnect-070.json).

## Broker observation

NAS100 minimum0.01-unit protected BUY LIMIT,500points below fresh bid,100point SL/TP distances and unchanged original60second GTD. Scope is the user's standing bounded demo-test authorization. Account49644649, order251110869. Broker reported ORDER_STATUS_EXPIRED with executedVolume0; update timestamp was1ms after the original expirationTimestamp. One entry record, zero management requests; no entry retry. Source-preserving100ms buffer held/released230quotes without pending data at shutdown.

Provider reconciliation failed while pending; monitor did not reach its20second automatic-cancel action. It reached terminal-unfilled review after broker expiry. Raw accepted event includes POSITION_STATUS_CREATED with zero volume/margin/commission/swap; no revision timestamp, so no authoritative position row was fabricated.

Fresh November21 history review072 confirmed one terminal order, no deals, no deposits/withdrawals, unchanged balance and balance version, and flat broker state. First review071 correctly rejected because its window started at probe completion rather than the earlier baseline economics timestamp; widened request starts at that actual baseline, then fresh evidence was recollected. No failed review was relabelled successful. Unfilled certificate is a scoped zero-activity review, not a fabricated positive-quantity Settlement or proof of fees for future trades.

Installed-runtime recovery073 returned COMPLETE. It then forced one real TCP abort while flat, reauthenticated generation1→3, and returned COMPLETE again without submit/manage calls. This is flat-account reconnect acceptance only. Original consumed entry and two prior completed test archives are retained.

Fresh broker probe074 on November21 reports flat USD10001.12 account; schedule interpreter returns SCHEDULED_CLOSED. No new proposal/order or expired proposal reuse attempted on Saturday. Automatic-cancellation retest and active-order disconnect validation await an open session and fresh causal quotes.

## Changes and tests

Added scoped UnfilledCertificate and strict reviewer: exact original order/owner, terminal zero execution, complete history from baseline, unchanged balance/version, no deals/cashflows/open exposure. Monitor may finish a reviewed unfilled lifecycle; cancellation outcome reconciliation and guarded cycle archive support that proof without inventing a position settlement.

Approval now pins pending_cancel_after_seconds20(default) or65(expiry trial with5second fallback after original60second GTD). Partial-fill cancellation and120second position cleanup remain unchanged. This schema addition changes approval hashes; don't silently renew old active approvals. The65second scenario is tested offline, not yet submitted to the broker.

Strict empty pending placeholders now separate from funded exposure only when linked to exactly one accepted, wholly unfilled same-symbol/same-side order, with explicit zero quantity, margin and costs. Optional P&L for such a placeholder must be explicitly zero. Nonzero/ambiguous/unlinked states still block. Provider retains the pending order as owned/external as appropriate. This reproduces a concrete compatibility gap with the observed event shape; missing raw reconciliation responses prevent conclusively attributing all historical pending failures to it.

Diagnostics now retain a bounded8-failure history, fixed error codes, safe exception type and phase, without raw broker exception text. Initial639tests+4subtests passed. Subsequent placeholder suite had649pass/1fail because an external-position test stub lacked its required status; updated it to an explicit OPEN position and added pending-provider coverage. Final651tests+4subtests passed in6.57s,11known warnings. Rebuilt final runtime source hash matched local source; actual unfilled recovery and flat reconnect passed. Pending-order compatibility fix still requires open-market runtime retest.

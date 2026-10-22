# Separate preparation evidence from first-order acceptance

The production DemoTransport gate requires all capability fields to be qualified. It remains unchanged. Protocol-compatible request encoding is not actual acceptance, and a first fill cannot be a prerequisite for collecting that same first-fill evidence. Do not resolve this cycle by marking protocol facts as demo observations.

## Before an attended first test

Require selected demo identity, explicit non-live binding, supported account/protection profile, account-bound price/volume grid, fresh quote/account/exposure, conservative complete planned-loss bound, proposal-specific margin, reviewed price/expiry constraints, one writer, durable intent/management handling, exact preview and explicit human authorization. Unknown mandatory sizing/protection facts still block. A small quantity does not substitute for a known upper cost bound.

## Observations produced by the test

Order acceptance/rejection, actual expiry, fills, returned protection, charged commission and cash settlement become test results. Missing observations remain missing: an unfilled order cannot qualify fee settlement or protection triggering. They determine later activation eligibility, not fabricated first-test inputs.

## Delivered in this change

`execution.bounded_demo.Controller` is a disabled rehearsal that persists non-executable action instructions in checkpoints. It has no broker transport, credentials, enabling flag or executable outbox writes. Its observations must be labelled deterministic_transport. It fixes EURUSD BUY LIMIT1000units,60second planned expiry and planned loss at mostUSD5AND0.1%equity. These input values are synthetic rehearsal facts, not independently valued live policy.

It records one submission instruction; never re-emits it after restart; cancels owned remainder at20seconds or on partial fill; plans immediate closure for unprotected owned positions and closure by120seconds otherwise. Cancellation/close instructions remain uncertain until fresh complete observations show terminal submission, zero owned exposure and complete settlement. Expiry alone does not imply flat. Disconnection/staleness inhibit actions; foreign exposure, excess quantity and clock rollback halt. Later contradictory exposure revokes completion. A crash after journaling leaves an uncertain instruction, not permission to resend.

## Still required for an enabled controller

An explicitly reviewed attended-test adapter must bind these instructions to the existing fenced durable transport/ownership ledger, enforce actual quote/valuation/policy/authorization at send time, and map broker evidence without caller assertions. That adapter and its independent qualification gate are **not implemented or enabled here**. Management timeout escalation and actual broker lifecycle acceptance remain open. Do not attach a generic callback to this rehearsal and call it qualified execution. Any enabled test remains subject to the bounded plan and explicit approval.

## Implementation follow-up — 2026-10-22

F6.4c binds actual read-only broker components; F6.4d supplies the disabled durable submission/owned-management adapter; F6.4e supplies timed reconciliation/cleanup. F6.4f adds the independent `FirstTestTransport` with an explicitly non-production Review and internally retained preview evidence. It does not invent first-fill observations or relax mandatory pre-trade facts. Production DemoTransport is unchanged. See `deploy/first-demo-qualification.md`. Reviewed real-account policy, actual bounded approval and broker lifecycle acceptance remain absent.

# First attended demo order qualification

Status: preparation only; actual orders remain disabled. Host: the selected Mac running Docker Desktop. Account: the selected demo account, privately bound in deployment configuration. Never use a live account or reuse a paper database.

## Before requesting authorization

- Full required strategy history and a bounded read-only shadow run must pass with current quotes, reconciliation and zero writes.
- Independently verify EURUSD tick size, unit/multiplier mapping, minimum/step, session, supported entry/expiry/protection parameters, trigger sides, commissions and settlement/conversion policy. Document sources and expiry; metadata precision alone is not proof of a tradable tick.
- Rebuild and test exact runtime/gateway images from the recorded source commit; use one isolated project, persistent private state and a single account writer. Verify authenticated controls and uncertainty recovery before activation.
- Confirm no unexplained existing orders or positions. Obtain fresh account economics and exact-quantity expected margin immediately before an entry. Expired evidence blocks the attempt.
- Keep the Mac awake, attended and on AC power; confirm Docker health and measured latency meet existing limits. Verify a halted local backup/restore and preserve rotated tokens.

## Proposed first authorization scope

One EURUSD entry at the broker's verified minimum quantity (currently observed as 1,000 units), at most one owned position and no automatic retry after an uncertain acknowledgement. Session maximum 15 minutes. Risk cap: USD 5 including the audited conservative fee/slippage envelope; if the minimum quantity and valid protective stop cannot fit, submit nothing. Exact order type, price, protective stop and expiry will be presented from fresh qualified inputs before authorization; they are not guessed here. No XAUUSD order, scaling, unrelated-order modification or autonomous continuation is included.

## Test sequence after explicit authorization

1. Record the authorization, account/environment identity, exact image/config hashes, fresh proposal and risk checks. Persist intent and fence before transport.
2. Send the one qualified minimum-size entry with supported broker-side protection. An unknown outcome inhibits entries and triggers reconciliation; never blindly resend.
3. Confirm broker order, fill quantity, ownership and active stop protection through observed events and reconciliation. A rejection is evidence, not a reason to change parameters and retry without review.
4. Close only the owned filled quantity after its required observations, or follow the approved recovery policy on missing protection. Confirm closure from complete matched deals and account reconciliation, including fees and released reservations.
5. End with no owned pending orders or positions and no unresolved submissions. Stop the isolated executor and retain state/evidence. If disconnection prevents cleanup, report unresolved exposure immediately and retain recovery state; stopping a container is not closure.

The first test validates a narrow entry/protect/exit path. Partial-fill, cancellation-race, disconnect-under-exposure, restart and nonempty-account valuation acceptance remain separate bounded test cases. Deterministic fault tests do not substitute for required actual broker evidence. Autonomous demo operation requires the complete qualification report; live trading remains outside scope.

## Current specification findings (2026-10-20)

The user-supplied FxPro pages corroborate EURUSD's 1,000-unit minimum/step and both symbols' USD 35/million/side commission. Account metadata reports zero minimum commission and zero P&L conversion fee rate for the selected USD account. Gold's published step conflicts with account metadata; it remains outside the first EURUSD-only test. The EURUSD page does not establish the tradable tick; exact per-fill rounding, settlement cash conventions and the limit/GTD protection profile still need account-specific qualification. Public sources are recorded in `docs/evidence/broker-specification-review.md`. These are concrete remaining evidence requirements, not a request to resupply application credentials.

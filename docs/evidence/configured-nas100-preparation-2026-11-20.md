# NAS100 configured demo preparation — 2026-11-20

Status: configuration draft only; no executable bundle, independent approval pins or order authorization issued. J06/J07 remain incomplete. Broker correspondence is optional.

## Proposed modeling inputs

These are assistant-proposed, provisional values for read-only review, not broker facts or accepted trading risk. They must be visible in the eventual exact J09 approval request.

| Setting | Proposed value / basis |
|---|---|
| Instrument | NAS100; native #USNDAQ100, historical symbol ID1107; must match fresh authenticated discovery |
| Account | Previously selected private demo identity; USD/HEDGED must be revalidated |
| Quantity | 0.01 units, conditional on current minimum/step confirmation |
| Grid | 0.01 for entry and absolute protection; configured applicability, informed by historical capture005 |
| Linear value | USD1 per unit per full index point; historical capture005 ratios, configured assumption |
| Fixed round-trip fee estimate | USD0.25; provisional nonzero modeling allowance, not observed commission |
| Per-unit/minimum fee | Zero additional modeled amount; fixed estimate above carries the fee assumption |
| Adverse-exit allowance | 50 index points, USD0.50 at quantity0.01/value1; provisional stress allowance, not guaranteed maximum slippage |
| Other-cost allowance | USD0.50 for financing, adjustments, rounding and delayed cleanup; provisional, not a broker ceiling |
| Illustrative stop | 100 index points produces USD1 price risk; total modeled loss USD2.25 including the above amounts. Not an entry proposal |
| Budget | Existing lesser-of USD5 and0.1%equity, plus10%margin reserve; use fresh economics |
| Operations | Protected BUY LIMIT, attached absolute SL/TP, original60second GTD, owned cancel/close; unknown acceptance explicitly retained |
| Settlement | DeferredCostPolicy; accounting stays unresolved until observed records support review |

Protection may fail or gaps/outages may exceed every allowance. Existing owned-exposure cleanup is required but cannot guarantee execution. A rejection or uncertain response permits no automatic replacement attempt. Known unsupported broker capabilities cannot be overridden.

## Connection evidence and next action

Probes042 and044 stopped in application-auth/discovery with a generic reason. Safe diagnostic043 authenticated successfully. Diagnostic045 initially included duplicate application authentication and was corrected; its corrected final run authenticated successfully and returned zero total accounts, not merely zero matching demo accounts. No account identifiers, tokens or server error descriptions were logged. The empty-list cause is unknown; token expiry, account expiry or broker fault has not been established.

The probe now reports NO_AUTHORIZED_ACCOUNTS for empty discovery and SELECTED_DEMO_ACCOUNT_UNAVAILABLE for an unavailable selected demo identity, rather than a generic qualification failure. These diagnostics do not weaken demo binding.

Restore account access through the cTrader authorization/account management flow, then repeat read-only discovery for the selected account. Do not overwrite rotated credentials with older seed tokens. Once access is present, verify current identity/geometry, assemble scoped expiring configuration and independent pins, and run a fresh proposal-bound preview. A different account requires a newly scoped profile, not silent substitution. J09 explicit order approval follows the successful preview.

## Runtime observations

Before the probe-only correction, local and installed Python source-tree hashes matched189321147cc9731b92eadf7c89e22575e6673c055ec64a950ade53440531e60e. Docker image trading-gateway:broker-configured inspected IDsha256:e0a7b458900dea64999244384cf65a2961ffb65a4eab6fff7f4993ee661e209f. These are historical runtime observations, not approval pins for modified source. Rebuild/recheck final runtime before bundle pinning. No orders sent.

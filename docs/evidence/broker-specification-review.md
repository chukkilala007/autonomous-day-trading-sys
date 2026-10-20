# Broker specification review — 2026-10-19

The private selected-account profile identifies FxPro. Public sources were inspected as corroboration; no account capability was automatically promoted and no order was sent.

- [EURUSD specification](https://www.fxpro.com/trading/forex/eurusd): cTrader section gives minimum/step of 1,000 EUR and minimum stop/limit distance of zero points. This corroborates sampled volume-grid metadata, but does not establish an account-bound tradable tick or every protection/expiry parameter.
- [Spot gold specification](https://www.fxpro.com/trading/metals/gold): lists a 0.01 minimum price fluctuation, 100 ounces per lot, USD 1 tick value per lot and a one-ounce minimum. Its displayed increase step is one lot, while the selected-account API exposes one-unit steps. The GOLD/XAUUSD mapping and this discrepancy need confirmation before treating the page as an executable account policy.
- [Commission and swap charges](https://www.fxpro.com/commissions-swap-charges): describes cTrader commission per side on USD-converted notional, and rollover charges. This is not complete evidence for per-fill minima, rounding, actual deal cash signs or all settlement fields. The historical and FAQ descriptions must not silently replace selected-account metadata.

Next: verify exact symbol specifications for the selected demo account, reconcile discrepancies, bind audited policy to the account and symbol with a validity interval, and retain fresh proposal-specific conversion/margin checks. Public indicative schedules alone do not prove the current broker session or override unknown holidays.

## User-supplied sources reconciled — 2026-10-20

The user supplied the two instrument URLs above and explicitly mapped GOLD to XAUUSD. Fresh private probe-015 independently identifies FxPro and the selected account. The new `gateways.ctrader.specifications` tool binds comparisons to that account, rejects old/foreign metadata and preserves conflicting values; its output is a review artifact, never an executable capability policy.

EURUSD minimum and step match at 1,000 underlying units. The lot size implied by the page's 0.01-lot minimum agrees with 100,000 units in the API. Gold's 100-ounce lot and one-ounce minimum agree; its public 100-ounce increment still conflicts with the API's one-ounce increment. Gold's published 0.01 tick is documented; EURUSD's page does not state a minimum price fluctuation. Display precision alone is not tick qualification.

Both instruments' precise metadata rate agrees with the commission page: USD 35 per million USD notional per side. The selected USD account reports zero minimum commission and zero P&L conversion fee rate. These facts narrow the cost audit, but do not prove per-fill rounding, complete settlement cash semantics or behavior under partial fills. No fees are replaced with a guessed round-trip allowance.

Actual evidence: private `specifications-015.json`; sanitized comparisons in `fxpro-specifications-015.json`. Remaining execution gates are retained.

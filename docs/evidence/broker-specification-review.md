# Broker specification review — 2026-10-19

The private selected-account profile identifies FxPro. Public sources were inspected as corroboration; no account capability was automatically promoted and no order was sent.

- [EURUSD specification](https://www.fxpro.com/trading/forex/eurusd): cTrader section gives minimum/step of 1,000 EUR and minimum stop/limit distance of zero points. This corroborates sampled volume-grid metadata, but does not establish an account-bound tradable tick or every protection/expiry parameter.
- [Spot gold specification](https://www.fxpro.com/trading/metals/gold): lists a 0.01 minimum price fluctuation, 100 ounces per lot, USD 1 tick value per lot and a one-ounce minimum. Its displayed increase step is one lot, while the selected-account API exposes one-unit steps. The GOLD/XAUUSD mapping and this discrepancy need confirmation before treating the page as an executable account policy.
- [Commission and swap charges](https://www.fxpro.com/commissions-swap-charges): describes cTrader commission per side on USD-converted notional, and rollover charges. This is not complete evidence for per-fill minima, rounding, actual deal cash signs or all settlement fields. The historical and FAQ descriptions must not silently replace selected-account metadata.

Next: verify exact symbol specifications for the selected demo account, reconcile discrepancies, bind audited policy to the account and symbol with a validity interval, and retain fresh proposal-specific conversion/margin checks. Public indicative schedules alone do not prove the current broker session or override unknown holidays.

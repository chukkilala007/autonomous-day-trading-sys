# NAS100 alternative: first read-only qualification

On2026-10-23 the selected FxPro demo account's authenticated symbol catalog mapped the requested NAS100 spot index to **#USNDAQ100**, symbol1107, description “US Nasdaq 100 Spot Index”. Dated #US100 futures also exist and were not selected. The cTrader MCP connection returned HTTP404 during initialization; direct Open API authentication and read-only discovery succeeded.

Probe034 collected current contract metadata, bracketed account economics and1,380 M1 history rows over the preceding24hours. This is observed history coverage, not an assertion that every minute is tradable or complete. Private probe data remains under var/sandbox-state; public contract/stream facts are summarized in nas100-readonly-035.json.

Observed wire volumes divide by100: lotSize100 =1unit/lot, minVolume1 =0.01units, stepVolume1 =0.01units, maxVolume50000 =500units. This is volume scaling only, not proof of the cash value per index point. Commission and precise commission rates, minimum commission and P&L conversion fee are all reported zero. Swap and rollover fields still exist; zero commission does not establish zero total trading cost. Metadata reports ENABLED, zero SL/TP minimum distances in POINTS, digits2 and pipPosition0. Digits2 is not independent TickSize evidence.

## Remaining work

- Selected-account Algo TickSize and monetary values captured on2026-10-23; review provenance and applicability to entry/protection grids.
- Establish account-currency value per unit per index point and a complete conservative cost bound, including spread/slippage and applicable financing/dividend or other index adjustments.
- Confirm attached SL/TP quote-side semantics and entry/GTD restrictions; later authorized orders must demonstrate acceptance and settlement.
- Configurable attended profile is implemented and tested offline (F6.4i). Supply a pinned reviewed NAS100 bundle with explicit quantity/value review before using it; no real-account executable bundle exists.
- Preserve the USD5AND0.1%equity ceiling and use a reviewed NAS100-specific quantity and geometry. No proposal, approval or executable policy has been created.

This investigation changes neither strategy support nor execution eligibility. No actual broker orders are authorized or submitted.

## Bounded quote/margin result

Run035 observed60.002seconds,159spots,zero callback errors and one FUTURE_QUOTE rejection with624microseconds source lead. No buffer was enabled or freshness check relaxed. Final quote valid, source age0.185522seconds at end. This is a bounded observation, not continuous-freshness or reconnect acceptance. Expected margin request for raw volume1 (=0.01units) returned1450 with moneyDigits2: USD14.50 for BUY and SELL. Request audit contains only authentication/read requests, rejected_writes0; no orders sent.

## Actual Algo capture004

Approved v2 ran locally and automatically stopped on2026-10-23. [Sanitized capture evidence](nas100-algo-capture-004.json) records TickSize0.01, TickValueUSD0.01, PipSize1 and PipValueUSD1; identity/nonce/time/volume importer checks passed. The ratio suggests USD1 per full index point per unit, classified as a startup snapshot pending review. No executable policy or broker acceptance is inferred.

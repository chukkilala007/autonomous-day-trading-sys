# Reviewed symbol and quantity for attended tests

The new ReviewedBundle profile `USD_linear_absolute_protected_buy_limit_gtd` binds the policy's exact broker instrument name/symbol ID, an explicit positive `quantity`, and a `contract_value_review` hash. All existing review hashes remain required. Currency and quote currency must both be USD. The supplied contract_value_per_unit must be independently reviewed as the linear account-currency value per unit per price increment; it is no longer assumed to be1. Nonlinear contracts and currency conversion remain unsupported here.

Quantity must lie on the reviewed volume grid and be representable in cTrader's hundredths-of-unit encoding. No default quantity is accepted for this new profile. NAS100's observed minimum0.01units encodes as1; this does not supply its unverified tick/value/cost policy. No deployable NAS100 review bundle is included.

The binding reads the exact configured broker symbol, requests expected margin for that quantity, and uses its quote stream and contract. The preview sizes exactly that quantity. First-test Review.symbol must match the bundle; Approval.quantity must match the bundle. Submission, owned cleanup and monitoring use the same quantity ceiling. The separate production capability gate is unchanged.

Limits remain BUY LIMIT with absolute SL/TP,60second original expiry,10second proposal collection window,2second quote/account freshness, USD5AND0.1%equity loss ceiling,10%equity margin reserve, one durable account-wide attempt,20second cancel/partial-fill cleanup and120second residual-position deadline. No symbol change permits a second attempt on an already-consumed account approval. All transports remain disabled by default.

The legacy EURUSD profile retains EURUSD/1000units/value1 restrictions. Added bundle fields alter canonical review hashes: recompute and independently review pins after schema migration; never automatically migrate an active approval. Synthetic test bundle values are not broker facts.

## NAS100 evidence collection route

The v2 read-only Algo exporter/importer now supports an explicit expected symbol and emits TickSize, TickValue, PipSize and PipValue with account identity, nonce and fresh probe matching. The installed v1 artifact remains EURUSD-only until v2 is imported. Capture on #USNDAQ100 locally; retain the source artifact digest and observed log. Do not simply relabel the old EURUSD capture.

The official [TickValue reference](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickValue/) describes a monetary tick value fixed at cBot startup. Consequently any derived TickValue/TickSize ratio is a timestamped candidate for review, not a continuously refreshed or broker-signed valuation. A fresh one-shot capture can narrow the point-value question; grid applicability, complete costs, protection/expiry semantics and actual acceptance remain separate checks.

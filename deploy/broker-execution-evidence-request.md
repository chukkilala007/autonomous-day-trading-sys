# Evidence needed before the first bounded demo order

Prepared for the operator; **not sent to the broker**. Scope: FxPro cTrader demo account 48232468, EURUSD first. Provide account-specific documentation or a broker response that identifies the environment, instrument and applicable date. Do not include credentials.

1. The selected-account Algo capture on2026-10-22 reports EURUSD TickSize0.00001. Confirm this is the minimum tradable price increment and whether that same grid applies to pending limit prices and absolute stop-loss/take-profit prices?
2. Confirm the account's EURUSD contract multiplier per unit, commission incidences and minimums, monetary rounding rules, conversion conventions and settlement treatment. The API reports USD35 per million USD per side and zero minimum commission; explain the notional price basis and when commission is charged/refunded for fills, partial fills and cancellations. Identify any additional applicable charges.
3. Confirm support for a 1,000-unit BUY LIMIT with attached absolute SL/TP and GOOD_TILL_DATE expiry. What minimum entry/protection distances and expiry restrictions apply? API SL/TP distances are currently zero, but this is not proof of order acceptance.
4. For attached protection on that LIMIT order, which quote side triggers the stop and target? Can the trigger method be selected at order creation, or does it require a later position amendment? The new-order `stopTriggerMethod` field is documented for pending STOP/STOP_LIMIT orders; we will not assume it selects attached LIMIT stop-loss behavior.
5. For later gold testing, resolve the XAUUSD volume-step discrepancy between the public GOLD cTrader specification and this account's API. State the account's canonical instrument mapping and volume units.

Protocol encoding is reviewed against [new-order messages](https://help.ctrader.com/open-api/messages/#protooaneworderreq) and [symbol metadata](https://help.ctrader.com/open-api/model-messages/#protooasymbol). Protocol support and broker statements are distinct from actual demo lifecycle observations. Neither authorizes submission. Some acceptance/settlement behavior can only be confirmed in a separately approved bounded test.

After documentation is obtained, bind it to reviewed policy inputs, implement any missing protection/profile restrictions in the executable path, and test the exact disabled bounded controller. Obtain fresh quote/account/margin data and present the final order preview for explicit approval. Do not label this report or a generic protocol mapping as `demo_observed` evidence.

## Research update — 2026-10-21

See [item-by-item investigation](../docs/evidence/broker-evidence-items-1-to-5.md) and fresh probe031 facts. Volume/lot scaling, reported commission basis/minimum, protocol order support and documented default SL sides now have sources. Narrow remaining requests to account-bound TickSize/grid applicability, exact rounding and partial-fill/cancellation/settlement conventions, TP quote-side semantics, account expiry/entry restrictions and the GOLD/XAUUSD step contradiction. Algo TickSize offers a read-only collection route; MCP currently omits it. The guide's suggested test trade and tolerance are not authorization or verified broker policy.

2026-10-22 update: actual account-bound TickSize capture and importer checks passed. Remaining questions above are still unsent; no broker contact or order submission is authorized by this document.

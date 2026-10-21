# Evidence needed before the first bounded demo order

Prepared for the operator; **not sent to the broker**. Scope: FxPro cTrader demo account 48232468, EURUSD first. Provide account-specific documentation or a broker response that identifies the environment, instrument and applicable date. Do not include credentials.

1. What is EURUSD's exact minimum tradable price increment on this account? Display digits and pip size alone do not establish the price grid. Does that same grid apply to pending limit prices and absolute stop-loss/take-profit prices?
2. Confirm the account's EURUSD contract multiplier per unit, commission incidences and minimums, monetary rounding rules, conversion conventions and settlement treatment. The API reports USD35 per million USD per side and zero minimum commission; explain the notional price basis and when commission is charged/refunded for fills, partial fills and cancellations. Identify any additional applicable charges.
3. Confirm support for a 1,000-unit BUY LIMIT with attached absolute SL/TP and GOOD_TILL_DATE expiry. What minimum entry/protection distances and expiry restrictions apply? API SL/TP distances are currently zero, but this is not proof of order acceptance.
4. For attached protection on that LIMIT order, which quote side triggers the stop and target? Can the trigger method be selected at order creation, or does it require a later position amendment? The new-order `stopTriggerMethod` field is documented for pending STOP/STOP_LIMIT orders; we will not assume it selects attached LIMIT stop-loss behavior.
5. For later gold testing, resolve the XAUUSD volume-step discrepancy between the public GOLD cTrader specification and this account's API. State the account's canonical instrument mapping and volume units.

Protocol encoding is reviewed against [new-order messages](https://help.ctrader.com/open-api/messages/#protooaneworderreq) and [symbol metadata](https://help.ctrader.com/open-api/model-messages/#protooasymbol). Protocol support and broker statements are distinct from actual demo lifecycle observations. Neither authorizes submission. Some acceptance/settlement behavior can only be confirmed in a separately approved bounded test.

After documentation is obtained, bind it to reviewed policy inputs, implement any missing protection/profile restrictions in the executable path, and test the exact disabled bounded controller. Obtain fresh quote/account/margin data and present the final order preview for explicit approval. Do not label this report or a generic protocol mapping as `demo_observed` evidence.

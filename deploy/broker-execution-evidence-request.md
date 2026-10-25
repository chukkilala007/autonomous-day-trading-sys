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

## NAS100 review update — 2026-10-23

Current first-test candidate is #USNDAQ100/1107 at0.01units; EURUSD/gold questions above are retained as history. [Review](../docs/evidence/nas100-policy-review.md) now supports captured tick/point units and documented TP sides. Do not keep TP quote-side documentation on the missing-information list; actual attached protection acceptance remains unobserved.

Narrow unsent account-specific questions:

1. Confirm TickSize0.01 applies to LIMIT entry and absolute SL/TP, and explain public USD1 tick-value terminology versus Algo TickValueUSD0.01/PipValueUSD1.
2. Confirm0.01unit BUY LIMIT with attached absolute SL/TP and60-second GOOD_TILL_DATE, minimum expiry lead, distances and default attached-stop trigger behavior.
3. Confirm zero reported commissions/conversion fees, rounding, partial-fill/cancel charges, and current financing/index-adjustment rules and times for this demo account.

Do not request or invent a guaranteed slippage ceiling: documented stops are not guaranteed. The proposed demo-only modeled-risk policy needs a separate decision and implementation; current complete-bound gate remains unchanged. No broker message has been sent.

## Narrowed J03/J04 request — 2026-10-24 (unsent)

V3 capture005 corroborates the prior NAS100 units; separate modeled demo policy is implemented offline. No actual assumptions are approved. Public zero index commission is now corroborated; do not ask the broker to repeat generic platform pricing. Request selected-account exceptions/applicability, monetary rounding and partial-fill/cancel charges; confirm the financing clock and DST mapping against the public 21:59 UK rule, plus index-adjustment server-midnight rules, calendar applicability and delayed-close charges. Retain the LIMIT/absolute SL/TP grid and public tick terminology questions. See [current review](../docs/evidence/nas100-contract-cost-review.md). No message has been sent.

## Consolidated current request — NAS100 (prepared, not sent)

Please confirm these conditions for our selected FxPro cTrader USD demo account, Open API48232468/native login10645472, symbol#USNDAQ100/1107. Please identify the applicable date/account scope. No credentials are needed.

1. Does the observed0.01price increment apply to BUY LIMIT entry and attached absolute stop-loss/take-profit? Confirm the contract cash value per unit per full index point, and clarify the public USD1tick label versus Algo TickSize0.01/TickValueUSD0.01/PipValueUSD1.
2. Is a0.01unit BUY LIMIT with attached absolute SL/TP and GOOD_TILL_DATE supported through Open API? Specify minimum remaining expiry lead and any entry/protection distances. Our proposal expires60seconds after creation, so remaining lead at receipt is shorter. Confirm default attached-stop trigger side/method; we do not interpret the STOP/STOP_LIMIT entry-trigger field as selecting attached LIMIT protection.
3. Confirm applicability of pending cancellation and full closure of this minimum-size position through Open API, including any account restrictions. We understand cancellation may race with execution and request acceptance is not proof of closure.
4. Confirm account-specific commission/minimum/fixed charges, partial-fill/cancel treatment and monetary rounding. Identify the authoritative deal fields/sign conventions for opening/closing commission, conversion charges and swap, whether closing commission includes opening charges, and whether separate cash entries must be reconciled.
5. Confirm financing and index-adjustment rates/calendars, charging clock/timezone/DST, withholding and delayed-close charges applicable to this account. Clarify the public21:59UK swap time and server-midnight dividend rule. We do not assume a short planned holding interval guarantees avoidance.

These answers support pre-test review. Actual order acceptance, fill/protection behavior and settlement remain observations for a separately authorized demo test. We are not requesting a guaranteed slippage ceiling. This request has not been transmitted.

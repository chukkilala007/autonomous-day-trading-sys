# Investigation of prepared evidence items 1–5

Reviewed 2026-10-21 using the supplied **FxPro cTrader EURUSD Contract Spec Guide.md** as research guidance, not as authorization to trade or send messages. Fresh account-bound Open API probe031 collected at21:51:42UTC. Sanitized values and source hash: [contract facts](broker-contract-facts-031.json). Account48232468; USD; orders disabled. No capability promotion or execution policy change.

## 1. Exact EURUSD price increment — still open

The selected account reports digits5/pipPosition4. Those are display/pip fields, not independent proof of the executable price grid. The connected MCP symbol-details response also exposes digits and pip size, but no tick-size field or account binding. It cannot close this question.

There is a better route than guessing from digits: the official Algo API exposes [Symbol.TickSize](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickSize/). Capture that property on the selected demo account with account identity, symbol and timestamp. This investigation did not run a cBot or obtain that value. Pending-limit and protection-grid applicability still needs account documentation or bounded acceptance evidence.

## 2. Contract, fees, conversion and settlement — substantially narrowed, not complete

Fresh account observations, normalized from raw volume cents:

| Item | EURUSD observation |
|---|---|
| One lot |100,000units|
| Minimum / increment / maximum |1,000 /1,000 /50,000,000units|
| Commission type |USD_PER_MILLION_USD|
| Precise commission rate |3,500,000,000 →35 after dividing by100,000,000|
| Minimum commission |0; CURRENCY; USD|
| Account currency / moneyDigits |USD /2|
| P&L conversion fee rate |0|
| Swap long / short |−0.89 /+0.19, PIPS|
| Triple-swap day / weekend charging |Wednesday /false|

FxPro's current [commission guide](https://www.fxpro.com/commissions-swap-charges) specifies USD35 per million USD notional, per side, with base notional converted to USD and then fees converted to account currency. Its EUR example converts100,000EUR at1.1685 to116,850USD and approximately4.09USD commission. For this USD account, no second USD-to-deposit-currency conversion is needed. An illustrative1,000EUR fill at1.1685 yields0.0408975USD before any rounding; this is not an executable cost quote. Opening and closing incur commissions. FxPro also documents overnight swaps and Wednesday triple swaps for FX/metals.

Corrections to the supplied guide: `moneyDigits=2` defines a0.01 monetary encoding unit, **not** a round-half-up/truncate rule. Read each deal's own moneyDigits. Lot size is units per lot, not a separate proof of every P&L/settlement convention. Rollover charges do not by themselves establish realized cash settlement. These distinctions follow the [official monetary field definitions](https://help.ctrader.com/open-api/model-messages/#protooadeal).

Still missing: precise rounding stage/mode, partial-fill aggregation, cancellation/refund treatment, actual charged-fee reconciliation and complete cash settlement. No new fills were created. The guide's older Japanese-domain press-release link was inaccessible; its claimed base-currency discrepancy was not independently confirmed and is not used to override current account metadata/current FxPro documentation. A suggested one-money-unit reconciliation tolerance is a proposal, not a broker-proven rounding rule.

## 3. 1,000-unit protected BUY LIMIT/GTD — documented support, acceptance open

The observed EURUSD grid permits1,000units; account metadata is HEDGED/FULL_ACCESS/not limited-risk, and the symbol is ENABLED. Reported SL/TP distances are0inPOINTS. The [new-order protocol](https://help.ctrader.com/open-api/messages/#protooaneworderreq) supports LIMIT, absolute stopLoss/takeProfit and GTD with expiry milliseconds. Installed SDK mappings were checked in execution-review030.

This does not establish an executable session, entry-price restrictions, minimum expiry lead or actual acceptance. Zero protection distances are reported metadata, not a promise that every placement is valid. The disabled controller, fresh margin/cost preview and explicit bounded-order authorization remain required.

## 4. Protection trigger sides and configuration — partial answer

Official [protection documentation](https://help.ctrader.com/ctrader/trading/protections/#stop-loss) says default Trade-side SL triggers on Bid for buys and Ask for sells; alternative opposite/double-tick choices exist. This establishes documented platform behavior, not an observed filled position on this account.

Open API new-order `stopTriggerMethod` is for pending STOP/STOP_LIMIT. It is not an attached-LIMIT SL selector. A position's protection can be changed through [ProtoOAAmendPositionSLTPReq.stopLossTriggerMethod](https://help.ctrader.com/open-api/messages/#protooaamendpositionsltpreq); inspect the returned position field to verify configuration. Do not omit initial protection and rely on a later amendment. The sources reviewed did not explicitly settle the requested TP quote-side semantics; keep that broker/acceptance question open rather than infer it from the SL setting.

## 5. Gold step and mapping — account value established; public contradiction remains

Fresh account metadata identifies XAUUSD(symbol41):100units per lot, minimum1unit, step1unit, maximum50,000units. MCP describes XAUUSD as Gold Ounce vs US Dollar and returns lot100/minimum1/step1, but its response lacks selected-account binding, so it is corroboration only.

The current [FxPro GOLD page](https://www.fxpro.com/trading/metals/gold) says100oz per lot, minimum1oz, but increment1lot. Thus its increment conflicts with the account's1-unit increment by a factor of100 under the GOLD/XAUUSD ounce mapping. The account-specific API is the operative observed grid; the public statement has not been explained or corrected. Keep the discrepancy visible and gold out of the first EURUSD-only order test. Broker confirmation should explicitly map GOLD↔XAUUSD and confirm units/increment.

## Next evidence to obtain

Capture account-bound Algo TickSize; obtain narrow broker answers on rounding/partial-fill fees, TP triggering, price/expiry restrictions and the gold contradiction. Use an explicitly authorized test later for actual order/protection/fee/settlement acceptance. No broker message or trade was sent in this investigation.

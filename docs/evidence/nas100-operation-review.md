# J05 operation review — 2026-10-24

Scope: selected FxPro USD demo, NAS100 / #USNDAQ100 / 1107, proposed 0.01-unit protected BUY LIMIT. Documentation review complete; exact account capability qualification BLOCKED. No request was sent and no runtime capability evidence was created.

## Protocol and implementation

The [Open API messages](https://help.ctrader.com/open-api/messages/#protooaneworderreq) specify LIMIT price, absolute stopLoss/takeProfit, GTD expiry in Unix milliseconds and volume in hundredths of a unit. Thus 0.01 units encodes as 1. New-order stopTriggerMethod describes STOP/STOP_LIMIT entry triggers, not attached LIMIT protection. Cancellation identifies account/order; closure identifies account/position/volume. All three writes require trade permission. These definitions establish protocol representation, not selected-account acceptance.

Repository orders.limit_fields emits BUY/LIMIT, absolute protection and the original expiry. first_test checks protocol_profile against installed SDK enums, the pinned review and fresh internal lease. No relative protection, market-entry substitution, retry or automatic expiry renewal is proposed.

## Broker documentation and remaining scope

[FxPro cTrader FAQ](https://www.fxpro.com/help-section/faq/ctrader-platform) describes creating pending LIMIT orders with volume, expiry and SL/TP together, cancelling pending orders and closing positions. This supports general platform availability. It does not state this account/symbol's minimum expiry lead or guarantee the precise 60-second combination. Its UI instructions do not establish Open API acceptance.

| Required operation | Available evidence | Qualification disposition |
|---|---|---|
| BUY_LIMIT_ABSOLUTE_SLTP_GTD_60S | Protocol fields plus general broker combined-order instructions | UNKNOWN for exact account scope; need applicable expiry/protection/grid restrictions |
| CANCEL_PENDING | Protocol cancellation and broker cTrader cancellation instructions | Documented generally; account-scoped evidence review still required |
| CLOSE_POSITION | Protocol closure and broker cTrader position-close instructions | Documented generally; account-scoped evidence review still required |

Do not label unknown as unsupported. Missing evidence does not establish a broker limitation. Do not fill broker_verified or demo_observed records from this report alone. A reviewed account-applicable broker statement can support preparation; actual acceptance is a J10/later output, not a prerequisite for all first tests.

[Official cTrader orders](https://help.ctrader.com/ctrader/trading/orders/) warns that an order triggered before expiry may fill after expiry. Cancellation likewise must be reconciled against fills. The existing ownership, uncertain-send journal and settlement controls remain necessary; a cancel response or elapsed timer cannot establish flatness.

## Unblock

Obtain account-applicable confirmation of the combined minimum-volume order, permitted expiry lead (including the controller's original sixty-second proposal with elapsed preparation time), attached-stop defaults and grid/distance constraints. Bind source, identity, symbol, review interval and independent hash to each operation claim. If unsupported, design and separately test an explicit alternative profile; never silently change order type or protection semantics. J03/J04 facts and J06 modeled assumptions remain separate.

Verification: inspect installed SDK mapping and run existing operation-plan/first-test/preflight regressions offline. No runtime change, no broker connection and no authorization.

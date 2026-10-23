# NAS100 policy evidence review — 2026-10-23

Status: reviewed observations and documented semantics; NOT an executable ReviewedBundle or order approval. Orders remain disabled. Scope: selected FxPro USD demo account, #USNDAQ100/1107, proposed quantity 0.01 units.

## Evidence disposition

| Item | Supported conclusion | Remaining boundary |
|---|---|---|
| Capture provenance | Capture004 came from the approved local v2 exporter, selected native demo account and symbol. Private probe, challenge, capture and importer file SHA256 values match the published manifest; artifact hash matches. Identity, nonce, time and volume checks passed at capture. | Local observation is not broker-signed. Preserve the original pending-review artifact; this review is a separate historical assessment, not a fresh valuation. |
| Price and monetary units | Account observation: TickSize 0.01, TickValue USD0.01, PipSize 1, PipValue USD1, lot 1 unit; minimum/step 0.01, maximum 500 units. TickValue/TickSize and PipValue/PipSize both imply USD1 per full price point per unit at startup. | Exact applicability of the tick grid to LIMIT and absolute SL/TP needs confirmation; monetary value is a startup snapshot. |
| Fees | Probe036 reports commission, precise commission rate, minimum commission and P&L conversion fee as zero. | These are reported fields, not observed charged settlement and not a complete cost bound. Rounding, partial-fill/cancellation treatment, financing and index adjustments remain to be scoped. |
| Protection | FxPro documents long TP triggering on Bid, short TP on Ask, with limit execution at target or better. Stop losses can execute adversely as market orders. | Documented behavior is not observed acceptance of this account's attached absolute protection. Do not interpret the pending-order stopTriggerMethod as proof of attached-stop behavior. |
| Expiry | cTrader documents expiry for pending LIMIT orders; a triggered order can still fill after expiry. | Account minimum expiry lead and exact protected LIMIT/GTD acceptance are unconfirmed. Expiry and cancel acknowledgement never prove flatness. |

Sources: [capture004 manifest](nas100-algo-capture-004.json), private probe036 and importer review004; [FxPro cTrader FAQ](https://www.fxpro.com/help-section/faq/ctrader-platform); [cTrader orders](https://help.ctrader.com/ctrader/trading/orders/); [Algo TickValue](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickValue/). Web documentation reviewed 2026-10-23; it does not identify this demo account.

The [public index specification](https://www.fxpro.com/trading/indices/usndaq100) corroborates minimum/step 0.01 and zero limit/stop level. Its label “1 tick value” says USD1, whereas the account Algo TickValue is USD0.01 with TickSize0.01. A full-point interpretation could explain this, but is an inference; do not substitute the public label for the captured unit definitions or claim the ambiguity resolved.

## Cost-policy mismatch

`gateways/ctrader/contract_builder.py` requires `classification=broker_verified` and `cost_coverage=complete_roundtrip_upper_bound`; its bounds explicitly include slippage. Probe036 reports guaranteedStopLoss=false. The documentation above provides no finite guaranteed adverse-fill bound. Therefore neither zero commission nor an estimated slippage allowance can truthfully satisfy that complete-bound classification. A different symbol alone does not solve this.

No deployable bundle was generated. Existing gates and runtime behavior remain unchanged. The USD5/equity0.1% sizing ceiling cannot be represented as an absolute guarantee on realized loss from a non-guaranteed stop.

## Recommended next implementation (not yet implemented)

Prepare a separately named, demo-only modeled-risk policy path, keeping production's verified-bound path unchanged. It must distinguish observed fee inputs from explicitly approved slippage assumptions and expose modeled loss versus uncapped adverse execution in the preview. No default allowance or automatic evidence promotion. Require an independently pinned review and explicit bounded approval before activation.

Acceptance work:

1. Define a versioned modeled-risk schema and review provenance. Reject it in production transport and prevent conversion to broker_verified complete-bound policy.
2. Retain the smaller of USD5 and equity0.1% as the modeled budget, exact minimum quantity, fresh margin/quote/account checks, one account-wide attempt, disabled defaults and ownership restrictions. No allowance value is chosen in this review.
3. Resolve grid/expiry and applicable fee/adjustment windows with account-specific evidence. Excluding rollover requires a verified calendar and a policy for delayed cleanup; a planned 120-second close cannot guarantee avoiding charges.
4. Test policy isolation, missing assumptions, stale evidence, cost arithmetic, exposure after expiry, and disabled activation. Reuse existing monitor/reconciliation tests where they already cover behavior.
5. Produce a fresh connected read-only preview, then present the exact proposed demo order and modeled-risk assumptions for authorization. Only a subsequent authorized test can establish actual acceptance, cleanup and settlement; do not require those observations to exist before the first test.

Operator decision needed before adopting modeled-risk activation: accept explicitly non-guaranteed demo loss modeling, or retain the current complete-bound requirement and keep broker writes blocked. This review does not select that policy on the operator's behalf. Broker questions remain unsent in the updated evidence request.

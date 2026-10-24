# J03 / J04 contract and cost review — 2026-10-24

Disposition: documentation review complete; account applicability gates remain BLOCKED. This is a review record, not an executable policy, capability claim or approval. Current candidate: selected FxPro USD demo account, NAS100 / #USNDAQ100 / 1107, minimum 0.01 units. Other brokers require their own evidence.

## J03: contract and units

[Capture005](nas100-algo-capture-005.json) records the approved v3 exporter run. All five private source-file hashes were rechecked against the manifest. Exact Decimal arithmetic confirms TickValue/TickSize = PipValue/PipSize = 1. Volume minimum/step 0.01, maximum 500 and lot size 1 are consistent with the previous capture. The capture is historical metadata; it does not establish current market availability.

The [official TickSize reference](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickSize/) identifies the property as the current symbol tick size. The [TickValue reference](https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/TickValue/) defines a startup monetary snapshot and demonstrates volume-in-units sizing using it. Together with the captured USD account/quote currencies, this supports the candidate USD1 per unit per full price point calculation. It does not resolve the conflicting public tick-value label or prove acceptance of every attached protection price.

| Fact | Disposition | Remaining action |
|---|---|---|
| Account/native-symbol/volume provenance | Reviewed local observation | Revalidate identity and geometry in the fresh binding |
| Tick 0.01 and candidate USD1/unit/point | Supported by capture and API definitions | Independent executable-policy review; preserve snapshot qualification |
| LIMIT and absolute SL/TP grid applicability | Unresolved | Account-applicable broker specification/response confirming 0.01 grid |
| Public USD1 tick label versus captured USD0.01 | Unresolved terminology | Clarify point/pip versus tick; do not overwrite observed values |
| Actual accepted prices and realized P&L | Unobserved | Collect in authorized J10/later lifecycle tests, not a circular precondition for J10 |

## J04: costs and event timing

[FxPro cTrader FAQ](https://www.fxpro.com/help-section/faq/ctrader-platform) documents floating spreads and zero commission for instruments outside FX/metals. This corroborates the zero commission fields recorded in the earlier selected-account probe; it is not an observed settlement or proof of zero total costs.

[FxPro commissions and swaps](https://www.fxpro.com/commissions-swap-charges) states automatic swap charging at 21:59 UK time. Treat this as a public rule requiring account applicability and timezone review, not a UTC cutoff. It does not establish cancellation fees or monetary rounding for this account.

[FxPro earnings calendar](https://www.fxpro.com/trading-tools/earnings-calendar) says positions held at server midnight on an ex-date receive/pay dividend adjustments, with withholding affecting buys. Calendar times default to GMT+2 unless indicated otherwise. Spot-index margin can change around corporate events. No actual upcoming NAS100 adjustment row was verified in this review; absence from extracted page text is not evidence of no event.

| Fact | Disposition | Remaining action |
|---|---|---|
| Index commission | Public zero-commission rule corroborates reported metadata | Account applicability review; later compare actual charges |
| Spread | Variable execution economics | Fresh two-sided quote and actual fills; do not invent a fixed zero cost |
| Monetary rounding and partial-fill/cancel charges | Unresolved | Account-specific conventions, including any minimum/fixed charge |
| Financing | Public charging time found | Confirm selected-account rate, clock/DST mapping and delayed-cleanup treatment |
| Index adjustments | Public rule found | Verify selected-symbol calendar, server timezone, withholding and applicable amounts |
| Settlement | No actual deal yet | J10/later tests must collect broker deal/cash records and reconcile, preserving unknown costs |

The planned 120-second cleanup does not guarantee avoidance of rollover or adjustments: disconnection or execution delay can extend exposure. An admission window alone cannot justify a complete cost bound. J01 now supplies separate demo modeled-risk semantics, but real adverse-exit and other-cost assumptions still need explicit review; none are chosen here. Production complete-bound semantics remain unchanged.

## Unblock and next cycle

Use the narrowed, unsent [evidence request](../../deploy/broker-execution-evidence-request.md) for the account-specific gaps. J03/J04 stay BLOCKED for qualification, rather than being marked DONE because research finished. Continue J05 protocol/broker operation review and inspect J06 prerequisites next. J08 offline launcher implementation is eligible if J06 remains blocked; J07 needs a reviewed bundle and fresh open-session data. J09 authorization is required before any J10 order. No broker message was sent.

Validation: five private source hashes and exact monetary ratios passed; primary source pages retrieved 2026-10-24. Documentation-only change; runtime baseline remains 562 tests plus 4 subtests from J01. No new broker connection, credential access, order, or capability promotion.

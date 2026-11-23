# TPR-2 preregistered test specification

Status: research and shadow qualification only. This document freezes the selected trend-pullback continuation variant before chronological testing. It does not claim profitability and does not authorize an order.

## Inherited causal signal rules

TPR-2 retains TPR-1's completed-data rules for confirmed M5 trend pivots, continuation impulse, frozen reclaimed swing zone, 30-minute forming expiry, completed M1 pullback rejection, structural invalidation, nearest causal M5/M15/H1 opposing target, minimum gross 2R, gap handling and conservative same-bar ambiguity. It uses the same fixed EURUSD and XAUUSD research tolerances and steps. TPR-1 code and behavior remain unchanged.

## Versioned material change

After a completed rejection, TPR-2 does not chase beyond the rejection candle. It offers a limit retest at the zone edge nearest the post-rejection market: zone upper edge for a long and zone lower edge for a short. The structural stop remains the whole-pullback extreme plus the existing two-step buffer. The target remains the nearest valid causal opposing level.

The limit is available only during the next two completed M1 bars and never beyond the original forming expiry. A limit and stop touch in the same bar is `AMBIGUOUS_TOUCH`; a stop-only touch invalidates; a limit-only touch is `ENTRY_TOUCHED`/missed in bar replay, never an assumed fill. Any gap blocks availability. A current executable quote already at or through the limit also blocks a fresh proposal.

For bid-basis candles, executable conversion is explicit: a long entry adds the observed bid/ask spread; a short stop and target add it. Grid, fresh provider quote time, actual session state, causal context completeness and cost gates must all pass. The proposal type is protected `limit`, never stop-limit.

## Qualification gates

1. Mechanics: deterministic causal unit tests, mirrored long/short behavior, prefix invariance, gap/expiry/ambiguity tests and exact proposal semantics.
2. Replay: untouched chronological data with no parameter changes; report detections and exclusions, not P&L where executable bid/ask history is absent.
3. Shadow: natural forward decisions with complete broker evidence, zero order writes and stable reconnect behavior.
4. Demo pilot: only after a fresh reviewed broker bundle, exact disabled-to-enabled pilot mandate, account/config/image pins and a new explicit authorization. Maximum one bounded entry.

Live mode is explicitly rejected. Any parameter or pattern change creates another strategy version and a new untouched evaluation period.

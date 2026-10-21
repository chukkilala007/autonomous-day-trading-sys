# Bounded causal buffering for read-only quotes

The operator approved bounded buffering on 2026-10-20 after measurements showed roughly 20ms host lag with automatic macOS synchronization enabled. Manual synchronization improved alignment but did not sustain the original zero-future-arrival criterion. Earlier failed runs remain failed.

## Opt-in profile

Only the read-only gateway service accepts `--quote-buffer-ms 100`. Default `0` retains immediate strict validation. This does not enable a demo order gateway or qualify any missing execution capability.

- Hold source timestamps at most 100ms ahead of local wall time.
- Keep at most 64 updates per symbol, in arrival order. A decreasing source timestamp rejects the pending sequence.
- Enforce a 250ms per-update residence deadline using a monotonic clock. Late callbacks and wall-clock regressions cannot extend this deadline.
- Block snapshots for that symbol while any update is pending, including use of an earlier accepted quote.
- Release only after local wall time reaches the original source timestamp, through the existing strict stream/Quote validator. Source timestamps and prices are unchanged. `Quote.received_at` records receipt into the validated feed at release; it is not the earlier network arrival time. Do not treat this as a network-latency measurement.
- Preserve each side's original source time. The existing two-second snapshot freshness limit remains unchanged; an old unchanged side cannot become fresh because a different side arrived.
- Clear/invalidate pending updates on excessive lead, overflow, malformed or out-of-order input, expired residence, invalid release, connection change, history repair reset and shutdown.
- Bind callbacks to the exact queue identity and session generation. Old callbacks cannot publish into a replacement queue.

Pending flags are persisted so RPC snapshots remain blocked throughout draining, including intermediate releases. Restart invalidates earlier quotes before clearing pending flags; no queue is recovered as accepted data.

## Diagnostics and acceptance

Reports expose the active profile and bounded queue counters. `buffered` and `released` are separate from rejection counts; drops include rejected incoming updates and queued updates. Reset drops during forced reconnect/shutdown are explicit, not silently treated as successful releases.

Offline acceptance covers exact release time, side ordering/freshness, every hard bound, malformed/foreign inputs, clock jumps, disconnect/generation changes, symbol isolation and restart. The installed gateway suite passed 288 tests and 4 subtests before online testing.

Prospective online check: 600-second read-only run with forced reconnect at 240 seconds, full strategy history, decision activity before/after repair, zero order writes, no strict-validator future-quote rejection at release, and no excessive-skew/overflow/expiry/out-of-order/release failure. Expected reconnect/shutdown resets are reported separately. Record quote availability rather than assuming every poll is fresh; ordinary stale/missing quotes still block decisions. A successful bounded-buffer check is not full S5/S6 acceptance or long-term operational soak.

The 100ms/250ms/64 profile is an explicit engineering bound, not inferred broker timestamp accuracy. Any future execution use or limit increase needs its own reviewed policy and qualification.

## Verification record

Final installed gateway regression: **290 passed + 4 subtests in 6.74s**. Fresh probe-022 qualified both bid bases. Run-019 was stopped after approximately44seconds because independent clock measurements showed128–130ms lag, outside this profile. It released11 buffered updates through strict validation and rejected75 excessive-skew updates, with zero broker writes. The planned reconnect was not reached. This is guard evidence only; ten-minute normal-condition acceptance is pending clock correction. No limits were widened.

Fresh acceptance on2026-10-21: separate single-symbol XAUUSD run-022 completed601.816seconds, forced reconnect PASS, full history and880shadow decisions across both workers. All1,288buffered updates released, zero quote rejections/drops/order writes. This closes the prospective bounded test for XAUUSD, not operational readiness. One collection failure and ordinary incomplete snapshots remain recorded. EURUSD run-021 remains blocked by an unexplained history gap. See `../evidence/restarted-xauusd-shadow-022.json` and the implementation tracker for sampling limitations and exact results. Earlier dual-symbol runs019/020 had invalid TPR instance configuration and cannot establish end-to-end acceptance.

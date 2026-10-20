# Online validation and remaining gates

Scope: selected cTrader demo account, Docker Desktop on the user's Mac. Broker tests in this round are read-only. No order authorization is inferred from the request to test online.

## Open blockers

| Gate | Missing evidence or implementation | Validation path |
|---|---|---|
| Sustained feed availability | Future-dated quotes and intermittent stale quotes | Measure host/guest clock alignment, correct underlying clock issues, repeat bounded and sustained shadow tests without relaxing freshness |
| EURUSD tick grid | Exact account tradable price increment | Account-bound native symbol evidence or broker confirmation; decimal display precision is insufficient |
| XAUUSD volume grid | Published step conflicts with API step | Resolve with account-specific broker evidence before gold execution |
| Execution economics | Full rounding, settlement, fill fees and applicable conversion conventions | Broker evidence plus controlled demo deal reconciliation |
| Margin | Sampled minimum/step quantities do not qualify all quantities or nonempty exposure | Fresh proposal-specific margin plus account-state validation |
| Market/session availability | Weekly schedule alone does not establish executable current state | Fresh account/symbol/feed checks and qualified broker behavior |
| Order capabilities | Limit/GTD expiry, attached SL/TP and trigger sides | Protocol mapping review followed by bounded demo lifecycle tests |
| Deployment policy | Complete account-bound executable policy and concrete test limits | Assemble from verified evidence; never promote unknown capabilities |
| Demo authorization | Earlier explicit orders-disabled instruction remains in effect pending clarification | Explicit authorization for concrete bounded demo-order test |
| TPR demo adapter | Paper stop-limit strategy differs from protected limit/GTD transport | Implement and qualify compatible strategy execution semantics |
| Actual execution lifecycle | Fills, partial fills, cancellation races, uncertain sends and protection recovery not qualified against broker | Authorized demo tests; label deterministic simulations separately where actual scenarios cannot be induced |
| Recovery with exposure | Actual broker history matching, settlement and restart reconciliation | Controlled owned exposure, forced disconnect/restart, no duplicate submission |
| Demo controls/dashboard | Order-facing controls, alerts and authoritative execution panels lack actual acceptance | Exercise after execution integration and authorization |
| Operational deployment | Representative demo soak, graceful upgrade/draining and single-writer recovery | Intended Mac/Docker topology with preregistered limits; account for host sleep |
| Off-host disaster recovery | Encrypted destination and actual key/restore exercise absent | Select destination, back up, restore isolated, then reconcile broker |
| Performance evaluation | S8.1 not implemented; no untouched evaluation evidence | Preregister data and criteria, then chronological cost-aware evaluation |
| Live mandate/activation | S8.2/S8.3 not implemented or authorized | Qualified release and explicit live instruction; outside demo testing |

Authentication, credentials, the choice of Mac as demo host, native AMD64/ARM64 builds, and historical coverage demonstrated in prior runs are not missing inputs. Historical successes do not substitute for fresh evidence.

## This round

- Fresh read-only probe-019: COLLECTED; order submission disabled.
- Host clock measurement before shadow: +0.105867 seconds behind network time, uncertainty 0.009047 seconds (`sntp -t 3 time.apple.com`; no clock modification).
- EURUSD shadow-013: full 400/80/24/16 history, 16 reconciliations and forced reconnect PASS. 213/215 updates rejected as FUTURE_QUOTE; zero complete snapshots, decisions or order writes. BLOCKED_FRESH_COVERAGE.
- Implementation baseline `74b6ed1` passed CI 39424940895, including native architecture, recovery, soak and open-exposure paper restart tests. These are offline/paper evidence, not broker execution acceptance.

XAUUSD shadow-014: full 400/80/24/16 history, 16 reconciliations and forced reconnect PASS. 665/668 updates rejected as FUTURE_QUOTE; zero complete snapshots, decisions or order writes. BLOCKED_FRESH_COVERAGE. Both drill stacks were removed; private evidence and rotated tokens preserved.

Installed gateway regression rerun after online tests: **271 passed, 4 subtests passed in 5.23s**. No source changes in this evidence-only feature.

User authorized preparing bounded demo testing, not submitting a specific order. See [prepared plan](../../deploy/bounded-demo-test-plan.md). Clock synchronization was requested locally because changing the system clock requires administrator access. Next fresh run identifiers: probe-020 and shadow-015.

Every stage retains its original acceptance criteria in the implementation tracker. A successful short read-only run cannot close S6, S7 or S8.

# TPR-2 v2 qualification schedule

The active untouched evaluation is `config/evaluation/tpr2-shadow-v2.json`. It starts at 07:00 Europe/London on 25 November 2026, runs for two weeks through 07:00 on 9 December 2026, and may extend unchanged for one further week through 07:00 on 16 December 2026. The original v1 contract and its evidence remain immutable historical records and are not combined into v2.

## Observation windows

Two non-overlapping four-hour bounded runs are scheduled each weekday for both EURUSD and XAUUSD:

| Window | Europe/London | Purpose |
|---|---|---|
| Morning | 07:00–11:00 Monday–Friday | London-session development and active European liquidity |
| Afternoon | 13:00–17:00 Monday–Friday | London/New York overlap and later-session behaviour |

Each scheduled run follows `deploy/tpr2-shadow-qualification.md`: fresh read-only probe, current image pins, distinct per-symbol analysis/state, exact XAUUSD closure handling, forced generation1→3 reconnect, orders disabled and clean shutdown before database inspection. A missed window is recorded as missed; it is not backfilled with overlapping or extended data.

Private schedule state is stored at `var/sandbox-state/tpr2-v2-campaign.json`. It records scheduled window IDs, project names, immutable image/source pins, private database/report paths and monitor disposition. It contains no credential values and remains excluded from Git.

## Monitoring windows

Monitoring runs at 11:15 and 17:15 each weekday. It checks that the corresponding gateway bound ended, stops remaining analysis containers, validates SQLite integrity, confirms gateway PASS/generation3/zero writes, copies the stopped databases, and regenerates the cumulative v2 report. It never opens an active bind-mounted WAL database and never places an order.

The monitor reports only meaningful state changes: failed/missed runs, integrity or reconnect failures, nonzero order-path evidence, new unique triggers/proposals, sample completion, start of the one-week extension, or a terminal qualification classification. Ordinary healthy WATCH-only accumulation may be summarized without repeated alerts.

The active thread automations are `tpr-2-morning-observation`, `tpr-2-afternoon-observation`, `tpr-2-morning-run-monitor` and `tpr-2-afternoon-run-monitor`. Their schedules use the user's Europe/London timezone.

## End and extension

At or after 07:00 on 9 December, the monitor produces the two-week assessment. A complete clean sample is `OPERATIONAL_SHADOW_PASS`. An otherwise clean but insufficient natural sample is `INCONCLUSIVE_EXTEND`, and the same schedule continues without parameter changes through 16 December. At or after that maximum date, an insufficient sample is `INCONCLUSIVE`. Any safety or evidence blocker remains `FAIL` and is not erased by later runs.

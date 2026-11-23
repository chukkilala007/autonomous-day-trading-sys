# Online cancellation and active-order reconnect qualification

On 2026-11-23 the bounded cTrader demo tests for automatic pending-order cancellation and disconnect/reconnect with an active order completed successfully on account `49644649` (`10655835`) using NAS100 at the broker minimum quantity of `0.01`.

The fresh read-only qualification ran for 120.9 seconds while the instrument was scheduled open. It observed 351 spot updates, 108 fresh samples and 66 fresh post-reconnect samples. Authentication advanced from generation 1 to 3, both generations repaired 120 M1 rows, and there were no quote rejections or read failures.

Test `nas100-demo-097` placed one far-away pending order. The normal monitor issued one automatic cancellation before broker expiry. Broker order `251130050` terminated `ORDER_STATUS_CANCELLED` with zero execution and zero cash change. Independent history certification and recovery then reached `COMPLETE` without another entry or cancellation.

Test `nas100-demo-100` placed one far-away pending order, waited for broker acceptance, then aborted the active TCP connection. The runtime reauthenticated (generation 1 to 3), resubscribed to spots, repaired feed coverage and resumed management. It did not resubmit the entry. The normal monitor issued one owned cancellation; broker order `251130127` terminated `ORDER_STATUS_CANCELLED` with zero execution and zero cash change. Independent history certification and recovery reached `COMPLETE`.

The final broker reconciliation was flat: balance, equity and free margin were all USD 10,001.12, with no open order or position. Private tokens, raw captures and per-test mandates are not published. The structured companion evidence records the reviewed image, source, bundle and policy hashes.

This qualifies the requested demo cancellation and active-pending-order reconnect paths only. It does not qualify a filled-position disconnect, protective-stop behavior, realized settlement, or live-account operation.

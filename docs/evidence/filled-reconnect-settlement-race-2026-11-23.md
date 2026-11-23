# Filled-position reconnect, settlement and cancellation-race qualification

On 2026-11-23 two additional bounded cTrader demo tests completed on account `49644649` (`10655835`) using the broker minimum NAS100 quantity of `0.01`.

Test `nas100-demo-103` filled entry order `251134898` at 25,847.25. Position `155953105` was observed with server stop 25,747.25, target 25,947.25 and `TRADE` stop-trigger method before the connection was deliberately interrupted. The runtime reauthenticated from generation 1 to 3, resubscribed and repaired market coverage without duplicating the entry. After the bounded holding deadline, it issued one owned close. Close order `251134991` filled the complete 0.01 at 25,864.00.

Independent settlement review found exactly two deals and reconciled USD 0.17 gross profit, zero commission, zero swap and zero conversion fee. The balance moved exactly from USD 10,001.12 to USD 10,001.29. Recovery reached `COMPLETE`, resolved the close journal and submitted no additional entry or close.

Test `nas100-demo-107` exercised the cancellation-versus-fill envelope with an accepted order one point below the current bid. One owned cancellation was invoked immediately after acceptance. The broker resolved order `251135078` as `CANCELLED` with zero execution and zero cash change. A transient unresolved-order state was preserved while broker history caught up, then independent certification and recovery reached `COMPLETE`; the cleanup journal is `TARGET_RESOLVED`.

The final account is flat at USD 10,001.29. This provides actual evidence for protected filled exposure across reconnect, owned closure and realized settlement, plus the cancel-first side of a cancellation/fill race. It does not claim an actually observed late fill after cancellation, a triggered stop/target, partial fill, general fee convention or live-account capability.

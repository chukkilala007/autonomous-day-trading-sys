"""Read-only minute-gap diagnosis; never creates or repairs a candle."""
from datetime import timedelta
from twisted.internet import defer
from trading_platform.contracts.values import digest, utc
from .audit import decode_ticks
from .normalization import integer


@defer.inlineCallbacks
def collect(session, symbol_id, start, now):
    start = utc(start)
    at = now()
    if start.second or start.microsecond or not timedelta(minutes=1) <= at-start <= timedelta(days=7):
        raise ValueError('recent completed aligned minute required')
    generation = session.generation
    first = int(start.timestamp()*1000); last = first+59999
    response = yield session.read('ProtoOAGetTrendbarsReq', symbolId=symbol_id, period=1,
                                  fromTimestamp=first, toTimestamp=last)
    # The pinned SDK has no hasMore field on trendbar responses. This exact
    # one-minute request can contain at most one M1 bar; explicit truncation rejects.
    if str(response.get('ctidTraderAccountId')) != str(session.account_id) or response.get('hasMore', False) is not False:
        raise ValueError('incomplete or foreign bar range')
    bars = response.get('trendbar', [])
    if len(bars) > 1 or any(integer(b['utcTimestampInMinutes'])*60000 != first for b in bars):
        raise ValueError('unexpected minute bar')
    sides = {}; hashes = {'bars': digest(response)}
    for side, kind in [('bid', 1), ('ask', 2)]:
        ticks = yield session.read('ProtoOAGetTickDataReq', symbolId=symbol_id, type=kind,
                                   fromTimestamp=first, toTimestamp=last)
        if str(ticks.get('ctidTraderAccountId')) != str(session.account_id) or ticks.get('hasMore') is not False:
            raise ValueError('incomplete or foreign tick range')
        decoded = decode_ticks(ticks, session.account_id, first, last) if ticks.get('tickData') else []
        sides[side] = len(decoded); hashes[side] = digest(ticks)
    if not session.ready or session.generation != generation:
        raise ValueError('gap audit connection changed')
    status = 'BAR_PRESENT' if bars else ('TICKS_WITHOUT_BAR' if any(sides.values()) else 'NO_TICKS_REPORTED')
    return dict(start=start.isoformat(), end=(start+timedelta(minutes=1)).isoformat(),
                observed_at=at.isoformat(), status=status, tick_counts=sides,
                bar_count=len(bars), response_hashes=hashes, repaired=False, orders_enabled=False)

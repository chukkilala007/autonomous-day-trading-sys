"""Read-only minute-gap diagnosis; never creates or repairs a candle."""
from datetime import timedelta
from twisted.internet import defer
from trading_platform.contracts.values import digest, utc
from .audit import decode_ticks
from .normalization import integer


@defer.inlineCallbacks
def collect(session, symbol_id, start, now, *, minutes=1):
    start = utc(start)
    at = now()
    if type(minutes) is not int or not 1 <= minutes <= 60:
        raise ValueError('bounded interval required')
    if start.second or start.microsecond or not timedelta(minutes=minutes) <= at-start <= timedelta(days=7):
        raise ValueError('recent completed aligned minute required')
    generation = session.generation
    first = int(start.timestamp()*1000); last = first+minutes*60000-1
    response = yield session.read('ProtoOAGetTrendbarsReq', symbolId=symbol_id, period=1,
                                  fromTimestamp=first, toTimestamp=last)
    # The pinned SDK has no hasMore field on trendbar responses. This exact
    # bounded request can contain at most 60 M1 bars; explicit truncation rejects.
    if str(response.get('ctidTraderAccountId')) != str(session.account_id) or response.get('hasMore', False) is not False:
        raise ValueError('incomplete or foreign bar range')
    bars = response.get('trendbar', [])
    stamps = [integer(b['utcTimestampInMinutes'])*60000 for b in bars]
    if len(bars) > minutes or len(set(stamps)) != len(stamps) or any(not first <= t <= last for t in stamps):
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
    return dict(start=start.isoformat(), end=(start+timedelta(minutes=minutes)).isoformat(),
                account_id=str(session.account_id), symbol_id=str(symbol_id),
                observed_at=at.isoformat(), status=status, tick_counts=sides,
                bar_count=len(bars), response_hashes=hashes, repaired=False, orders_enabled=False)

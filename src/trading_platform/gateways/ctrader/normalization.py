"""Explicit protocol units; digits never imply a tradable tick grid."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from trading_platform.contracts.events import Bar, Quote


def integer(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)): raise ValueError('protocol integer required')
    try: result=int(value)
    except (TypeError,ValueError): raise ValueError('protocol integer required') from None
    if isinstance(value,str) and str(result)!=value: raise ValueError('noncanonical integer')
    return result


def relative_price(value):
    price=Decimal(integer(value))/Decimal(100000)
    if price<=0: raise ValueError('positive price required')
    return price


def units(value):
    quantity=Decimal(integer(value))/Decimal(100)
    if quantity<=0: raise ValueError('positive volume required')
    return quantity


def wire_volume(quantity):
    if not isinstance(quantity,Decimal) or not quantity.is_finite() or quantity<=0 or quantity*100 != (quantity*100).to_integral_value():
        raise ValueError('volume is not representable in protocol units')
    return int(quantity*100)


def timestamp_ms(value):
    return datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=integer(value))


def spot(symbol,raw,received):
    # A one-sided update cannot establish the freshness of the other side.
    if not all(k in raw for k in ('bid','ask','timestamp')): raise ValueError('incomplete spot')
    return Quote(instrument=symbol,bid=relative_price(raw['bid']),ask=relative_price(raw['ask']),source_time=timestamp_ms(raw['timestamp']),received_at=received)


def trendbar(symbol,raw,minutes,received,*,basis):
    if basis not in ('bid','ask'): raise ValueError('verified candle basis required')
    if type(minutes)!=int or minutes<=0: raise ValueError('fixed timeframe required')
    start=timestamp_ms(integer(raw['utcTimestampInMinutes'])*60000)
    end=start+timedelta(minutes=minutes)
    if end>received: raise ValueError('unfinished bar')
    low=integer(raw['low'])
    return Bar(instrument=symbol,start=start,end=end,available_at=received,basis=basis,
        low=relative_price(low),open=relative_price(low+integer(raw['deltaOpen'])),
        high=relative_price(low+integer(raw['deltaHigh'])),close=relative_price(low+integer(raw['deltaClose'])))

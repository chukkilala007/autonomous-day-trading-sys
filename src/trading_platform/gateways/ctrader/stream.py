"""Read-only SDK stream bridge. Reconnect history must complete before coverage."""
from datetime import timedelta
from collections import Counter
from twisted.internet import defer
from .normalization import spot,trendbar
from .history import complete_range

PERIODS={1:1,5:5,15:7,30:8,60:9,240:10,1440:12}


class Stream:
    def __init__(self,session,feed,symbols,requirements,now):
        self.session=session;self.feed=feed;self.symbols=symbols;self.requirements=requirements;self.now=now
        self.spot_rejections=Counter()
        self.failures={};self.busy=False;self.subscribed_generation=None;self.last_complete={};self.quote_sides={}
        for symbol,basis,minutes,count in requirements:
            if minutes not in PERIODS or count<=0 or count>1000: raise ValueError('unsupported history request')
            if symbol not in symbols or basis not in ('bid','ask'): raise ValueError('unverified symbol or basis')

    def disconnected(self):
        self.subscribed_generation=None;self.last_complete={};self.quote_sides={}
        for symbol in self.symbols: self.feed.disconnect(symbol)

    @defer.inlineCallbacks
    def repair(self):
        if self.busy: return
        self.busy=True;generation=self.session.generation
        cold=self.subscribed_generation!=generation
        if cold: self.disconnected()
        try:
            if cold:
                yield self.session.read('ProtoOASubscribeSpotsReq',symbolId=list(self.symbols.values()),subscribeToSpotTimestamp=True)
            at=self.now()
            for symbol,basis,minutes,count in self.requirements:
                key=(symbol,basis,minutes,count)
                previous=self.last_complete.get(key)
                if previous and at<previous: raise ValueError('feed clock regression')
                start=(previous-timedelta(minutes=minutes*2)) if previous else (at-timedelta(minutes=minutes*(count+2)))
                rows=yield complete_range(self.session,'ProtoOAGetTrendbarsReq','trendbar',int(start.timestamp()*1000),int(at.timestamp()*1000),symbolId=self.symbols[symbol],period=PERIODS[minutes])
                received=self.now()
                for raw in rows:
                    # Current unfinished bar is not a closed-bar event.
                    start=int(raw['utcTimestampInMinutes'])*60
                    if start+minutes*60>at.timestamp(): continue
                    self.feed.ingest_bar(trendbar(symbol,raw,minutes,received,basis=basis))
                # Advance only after a fully completed page range. Coverage still checks gaps.
                history=self.feed.snapshot(received,[(symbol,basis,minutes,count)])
                if len(history.bars)==count: self.last_complete[key]=at
                else: self.last_complete.pop(key,None)
            if generation!=self.session.generation or not self.session.ready: raise ValueError('disconnected during repair')
            for symbol in self.symbols: self.feed.repaired(symbol,at)
            self.subscribed_generation=generation
            self.failures={}
        except Exception:
            self.disconnected();self.failures={'feed':'HISTORY_REPAIR_REQUIRED'}
            raise
        finally: self.busy=False

    def on_spot(self,raw):
        if str(raw.get('ctidTraderAccountId'))!=str(self.session.account_id): raise ValueError('foreign account feed')
        symbol=next((s for s,id in self.symbols.items() if str(id)==str(raw.get('symbolId'))),None)
        if symbol is None: raise ValueError('unknown symbol')
        reason='INVALID_SPOT'
        try:
            from .normalization import timestamp_ms,relative_price
            from trading_platform.contracts.events import Quote
            if 'timestamp' not in raw or not any(side in raw for side in ('bid','ask')):
                reason='MISSING_SPOT_FIELDS'
                raise ValueError('missing quote timestamp or side')
            at=timestamp_ms(raw['timestamp']);sides=dict(self.quote_sides.get(symbol,{}))
            for side in ('bid','ask'):
                if side in raw:
                    if side in sides and at<sides[side][1]:
                        reason='OUT_OF_ORDER_SIDE'
                        raise ValueError('out-of-order quote side')
                    sides[side]=(relative_price(raw[side]),at)
            self.quote_sides[symbol]=sides
            if len(sides)<2:return
            # Never make an unchanged side look newer than its actual observation.
            received=self.now();source=min(v[1] for v in sides.values())
            if sides['bid'][0]>sides['ask'][0]:reason='CROSSED_QUOTE'
            elif received<source:reason='FUTURE_QUOTE'
            quote=Quote(instrument=symbol,bid=sides['bid'][0],ask=sides['ask'][0],source_time=source,received_at=received)
            self.feed.ingest_quote(quote)
        except ValueError as error:
            if str(error)=='old quote':reason='OUT_OF_ORDER_QUOTE'
            self.spot_rejections[reason]+=1
            self.feed.disconnect(symbol);self.failures[symbol]='INCOMPLETE_OR_STALE_SPOT'

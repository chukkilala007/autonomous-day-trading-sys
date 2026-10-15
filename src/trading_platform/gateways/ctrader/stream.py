"""Read-only SDK stream bridge. Reconnect history must complete before coverage."""
from datetime import timedelta
from twisted.internet import defer
from .normalization import spot,trendbar
from .history import complete_range

PERIODS={1:1,5:5,15:7,30:8,60:9,240:10,1440:12}


class Stream:
    def __init__(self,session,feed,symbols,requirements,now):
        self.session=session;self.feed=feed;self.symbols=symbols;self.requirements=requirements;self.now=now
        self.failures={};self.busy=False
        for symbol,basis,minutes,count in requirements:
            if minutes not in PERIODS or count<=0 or count>1000: raise ValueError('unsupported history request')
            if symbol not in symbols or basis not in ('bid','ask'): raise ValueError('unverified symbol or basis')

    def disconnected(self):
        for symbol in self.symbols: self.feed.disconnect(symbol)

    @defer.inlineCallbacks
    def repair(self):
        if self.busy: return
        self.busy=True;self.disconnected();generation=self.session.generation
        try:
            yield self.session.read('ProtoOASubscribeSpotsReq',symbolId=list(self.symbols.values()),subscribeToSpotTimestamp=True)
            at=self.now()
            for symbol,basis,minutes,count in self.requirements:
                rows=yield complete_range(self.session,'ProtoOAGetTrendbarsReq','trendbar',int((at-timedelta(minutes=minutes*(count+2))).timestamp()*1000),int(at.timestamp()*1000),symbolId=self.symbols[symbol],period=PERIODS[minutes])
                received=self.now()
                for raw in rows:
                    # Current unfinished bar is not a closed-bar event.
                    start=int(raw['utcTimestampInMinutes'])*60
                    if start+minutes*60>at.timestamp(): continue
                    self.feed.ingest_bar(trendbar(symbol,raw,minutes,received,basis=basis))
            if generation!=self.session.generation or not self.session.ready: raise ValueError('disconnected during repair')
            for symbol in self.symbols: self.feed.repaired(symbol,at)
            self.failures={}
        except Exception:
            self.disconnected();self.failures={'feed':'HISTORY_REPAIR_REQUIRED'}
            raise
        finally: self.busy=False

    def on_spot(self,raw):
        if str(raw.get('ctidTraderAccountId'))!=str(self.session.account_id): raise ValueError('foreign account feed')
        symbol=next((s for s,id in self.symbols.items() if str(id)==str(raw.get('symbolId'))),None)
        if symbol is None: raise ValueError('unknown symbol')
        try: self.feed.ingest_quote(spot(symbol,raw,self.now()))
        except ValueError:
            self.feed.disconnect(symbol);self.failures[symbol]='INCOMPLETE_OR_STALE_SPOT'

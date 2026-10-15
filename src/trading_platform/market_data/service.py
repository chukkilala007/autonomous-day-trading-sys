"""Durable causal feed cache and reconnect coverage, independent of strategies."""
import json
from datetime import timedelta
from trading_platform.contracts.events import Bar, Quote
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.values import canonical,digest


class Feed:
    def __init__(self,db): self.db=db

    def put(self,key,value):
        with self.db.transaction() as c: c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(key,canonical(value)))

    def get(self,key):
        r=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
        return json.loads(r['body']) if r else None

    def ingest_bar(self,bar):
        key='bar:'+digest((bar.instrument,bar.basis,bar.start,bar.end))
        old=self.get(key)
        with self.db.transaction() as c:
            if old:
                prior=Bar.model_validate_json(json.dumps(old))
                if prior.model_copy(update={'available_at':bar.available_at})==bar: return False
                if bar.available_at<prior.available_at: raise ValueError('old revision')
                c.execute('INSERT INTO revisions(old_hash,new_hash) VALUES (?,?)',(digest(prior),digest(bar)))
                c.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest(prior),canonical(prior)))
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(key,canonical(bar)))
        return True

    def ingest_quote(self,quote):
        old=self.get('quote:'+quote.instrument)
        if old and Quote.model_validate_json(json.dumps(old)).source_time>quote.source_time: raise ValueError('old quote')
        self.put('quote:'+quote.instrument,quote)

    def disconnect(self,symbol): self.put('coverage:'+symbol,{'repaired':False})

    def repaired(self,symbol,at): self.put('coverage:'+symbol,{'repaired':True,'at':at})

    def snapshot(self,cutoff,requirements,*,closed_intervals=(),max_quote_age=2):
        """requirements: (symbol,basis,minutes,count); closures must be verified."""
        bars=[];quotes=[];complete=True
        all_bars=[Bar.model_validate_json(r['body']) for r in self.db.connection.execute("SELECT body FROM checkpoints WHERE id LIKE 'bar:%'")]
        for symbol,basis,minutes,count in requirements:
            if type(minutes)!=int or minutes<=0 or type(count)!=int or count<=0: raise ValueError('history requirement')
            coverage=self.get('coverage:'+symbol)
            if not coverage or not coverage['repaired']: complete=False
            step=timedelta(minutes=minutes)
            series=sorted((b for b in all_bars if b.instrument==symbol and b.basis==basis and b.end-b.start==step and b.available_at<=cutoff),key=lambda b:b.start)
            by_end={b.end:b for b in series}
            end=cutoff.replace(second=0,microsecond=0)
            end-=timedelta(minutes=int(end.timestamp()/60)%minutes)
            selected=[];scanned=0
            while len(selected)<count and scanned<count+10000:
                start=end-step;scanned+=1
                closed=any(s==symbol and a<=start and end<=z for s,a,z in closed_intervals)
                if not closed:
                    if end not in by_end: complete=False;break
                    selected.append(by_end[end])
                end=start
            if len(selected)!=count: complete=False
            bars.extend(selected)
        for symbol in sorted({r[0] for r in requirements}):
            raw=self.get('quote:'+symbol)
            if raw:
                quote=Quote.model_validate_json(json.dumps(raw))
                if quote.received_at<=cutoff and 0<=(cutoff-quote.source_time).total_seconds()<=max_quote_age: quotes.append(quote)
                else: complete=False
            else: complete=False
        unique={digest(b):b for b in bars}
        return Snapshot(cutoff=cutoff,bars=tuple(sorted(unique.values(),key=lambda b:(b.instrument,b.start,b.basis))),quotes=tuple(quotes),coverage_complete=complete)


def subscriptions(instances,manifests):
    requests={}
    for instance in instances:
        for timeframe,count in manifests[instance.strategy].history:
            for symbol in instance.universe:
                key=(symbol,timeframe)
                requests[key]=max(requests.get(key,0),count)
    return requests


def history_window(last_complete,now,minutes):
    if now<last_complete: raise ValueError('clock regression')
    return last_complete-timedelta(minutes=minutes),now

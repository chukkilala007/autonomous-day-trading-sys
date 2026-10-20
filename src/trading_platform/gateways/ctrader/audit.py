"""Read-only capability evidence. Missing execution facts stay explicit blockers."""
from datetime import timedelta
from decimal import Decimal
from twisted.internet import defer
from trading_platform.contracts.values import digest,utc,canonical
from .metadata import CapabilityReport,Evidence
from .normalization import integer,units


def decode_ticks(response,account,start,end):
    if str(response.get('ctidTraderAccountId'))!=str(account) or response.get('hasMore') is not False:
        raise ValueError('incomplete or foreign ticks')
    rows=[];timestamp=price=0
    for i,raw in enumerate(response.get('tickData',[])):
        delta=integer(raw['timestamp'])
        if i and delta>0: raise ValueError('tick chronology')
        timestamp+=delta;price+=integer(raw['tick'])
        if not start<=timestamp<=end or price<=0: raise ValueError('invalid tick range or price')
        rows.append((timestamp,price))
    if not rows: raise ValueError('empty tick sample')
    return list(reversed(rows))


def matches_bar(bar,ticks):
    low=integer(bar['low']);prices=[p for _,p in ticks]
    return [prices[0],max(prices),min(prices),prices[-1]]==[
        low+integer(bar['deltaOpen']),low+integer(bar['deltaHigh']),low,low+integer(bar['deltaClose'])]


def quote_ohlc(sides,start,end):
    """Reconstruct each side at the first observed bid OR ask event.

    Independent tick series omit unchanged prices. Carry only a known earlier
    tick; conflicting equal-time updates are ambiguous and must reject.
    """
    events=sorted({at for ticks in sides.values() for at,_ in ticks if start<=at<=end})
    if not events:raise ValueError('empty quote interval')
    result={}
    for side,ticks in sides.items():
        by_time={}
        for at,price in ticks:
            if at in by_time and by_time[at]!=price:raise ValueError('ambiguous same-time ticks')
            by_time[at]=price
        earlier=[at for at in by_time if at<=events[0]]
        if not earlier:raise ValueError('missing preceding side quote')
        prices=[by_time[max(earlier)]]+[p for at,p in sorted(by_time.items()) if events[0]<at<=end]
        result[side]=[prices[0],max(prices),min(prices),prices[-1]]
    return result


@defer.inlineCallbacks
def collect(session,probe,now):
    generation=session.generation;at=now();account=str(session.account_id)
    if probe['account_id']!=account: raise ValueError('foreign probe')
    metadata={str(s['symbolId']):s for s in probe['metadata']['symbol']}
    reports={}
    for name,sid in probe['symbols'].items():
        raw=metadata[str(sid)];evidence=[]
        def add(field,value):
            evidence.append(Evidence(field=field,value=value,source='demo_metadata_and_tick_audit',observed_at=at,valid_until=at+timedelta(hours=24),classification='demo_observed'))
        add('account_type',probe['economics']['trader']['accountType']);add('symbol_id',str(sid))
        grid={key:str(units(raw[field])) for key,field in (('min','minVolume'),('max','maxVolume'),('step','stepVolume'))}
        if Decimal(grid['min'])>Decimal(grid['max']):raise ValueError('invalid volume grid')
        add('volume_grid',canonical(grid))
        samples=[]
        bars=sorted((b for b in probe['trendbars'][name] if integer(b['utcTimestampInMinutes'])*60+60<=at.timestamp()),key=lambda b:integer(b['utcTimestampInMinutes']))[-3:]
        for bar in bars:
            start=integer(bar['utcTimestampInMinutes'])*60000;end=start+59999
            sample={'minute':bar['utcTimestampInMinutes'],'matches':{},'tick_counts':{},'hashes':{},'tick_ohlc':{},'bar_ohlc':[integer(bar['low'])+integer(bar[k]) for k in ('deltaOpen','deltaHigh')]+[integer(bar['low']),integer(bar['low'])+integer(bar['deltaClose'])]}
            sides={}
            for side,kind in [('bid',1),('ask',2)]:
                response=yield session.read('ProtoOAGetTickDataReq',symbolId=sid,type=kind,fromTimestamp=start-60000,toTimestamp=end)
                ticks=decode_ticks(response,account,start-60000,end)
                sides[side]=ticks
                current=[(t,p) for t,p in ticks if start<=t<=end]
                sample['tick_ohlc'][side]=[current[0][1],max(p for _,p in current),min(p for _,p in current),current[-1][1]] if current else None
                sample['matches'][side]=bool(current) and matches_bar(bar,current);sample['tick_counts'][side]=len(current);sample['hashes'][side]=digest(response)
            try:
                sample['quote_ohlc']=quote_ohlc(sides,start,end)
                sample['quote_matches']={side:ohlc==sample['bar_ohlc'] for side,ohlc in sample['quote_ohlc'].items()}
            except ValueError:sample['quote_matches']={}
            samples.append(sample)
        basis='bid' if len(samples)==3 and all(s['quote_matches']=={'bid':True,'ask':False} for s in samples) else None
        if basis:add('candle_basis',basis)
        report=CapabilityReport(account_id=account,symbol=name,evidence=tuple(evidence))
        # Metadata values are recorded, not promoted into complete cost/contract policies.
        observed={k:raw[k] for k in ('digits','lotSize','commissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionType','minCommissionAsset','pnlConversionFeeRate','slDistance','tpDistance','distanceSetIn','tradingMode','leverageId') if k in raw}
        reports[name]={'capability':report.model_dump(mode='json'),'execution_blockers':report.blockers(now(),account,name),'observed_metadata':observed,'candle_samples':samples,'read_only_basis':basis}
    if session.generation!=generation or not session.ready:raise ValueError('audit connection changed')
    return dict(account_id=account,observed_at=at.isoformat(),symbols=reports,orders_enabled=False,qualification_complete=False,evidence_hash=digest(reports))


@defer.inlineCallbacks
def collect_margins(session,probe,now):
    """Observe exact-volume expected margins; does not certify contract sizing."""
    from .costs import expected_margin
    generation=session.generation;results={}
    if probe['account_id']!=str(session.account_id):raise ValueError('foreign margin probe')
    metadata={integer(s['symbolId']):s for s in probe['metadata']['symbol']}
    for name,symbol in probe['symbols'].items():
        raw=metadata[symbol];minimum=integer(raw['minVolume']);step=integer(raw['stepVolume']);maximum=integer(raw['maxVolume'])
        if minimum<=0 or step<=0 or maximum<minimum:raise ValueError('invalid margin grid')
        volumes=[minimum+n*step for n in range(3) if minimum+n*step<=maximum]
        request=dict(ctidTraderAccountId=session.account_id,symbolId=symbol,volume=volumes)
        at=now()
        response=yield session.read('ProtoOAExpectedMarginReq',symbolId=symbol,volume=volumes)
        if not session.ready or session.generation!=generation:raise ValueError('margin connection changed')
        normalized=dict(ctidTraderAccountId=integer(response['ctidTraderAccountId']),moneyDigits=integer(response['moneyDigits']),margin=[{k:integer(row[k]) for k in ('volume','buyMargin','sellMargin')} for row in response['margin']])
        checked=now();rows=[]
        for volume in volumes:
            values={side.lower():str(expected_margin(normalized,request=request,account=session.account_id,symbol_id=symbol,volume=volume,side=side,observed_at=at,now=checked)) for side in ('BUY','SELL')}
            rows.append(dict(quantity=str(units(volume)),**values))
        results[name]=dict(observed_at=at.isoformat(),checked_at=checked.isoformat(),currency=probe['economics']['account']['currency'],rows=rows,evidence_hash=digest(dict(request=request,response=response)),classification='demo_observed',scope='exact_sampled_volumes_only')
    return dict(symbols=results,orders_enabled=False,qualification_complete=False)

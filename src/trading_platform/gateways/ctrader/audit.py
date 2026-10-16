"""Read-only capability evidence. Missing execution facts stay explicit blockers."""
from datetime import timedelta
from decimal import Decimal
from twisted.internet import defer
from trading_platform.contracts.values import digest,utc
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
        grid={key:str(units(raw[key])) for key in ('minVolume','maxVolume','stepVolume')}
        if Decimal(grid['minVolume'])>Decimal(grid['maxVolume']):raise ValueError('invalid volume grid')
        add('volume_grid',str(grid))
        samples=[]
        bars=sorted((b for b in probe['trendbars'][name] if integer(b['utcTimestampInMinutes'])*60+60<=at.timestamp()),key=lambda b:integer(b['utcTimestampInMinutes']))[-3:]
        for bar in bars:
            start=integer(bar['utcTimestampInMinutes'])*60000;end=start+59999
            sample={'minute':bar['utcTimestampInMinutes'],'matches':{},'tick_counts':{},'hashes':{}}
            for side,kind in [('bid',1),('ask',2)]:
                response=yield session.read('ProtoOAGetTickDataReq',symbolId=sid,type=kind,fromTimestamp=start,toTimestamp=end)
                ticks=decode_ticks(response,account,start,end)
                sample['matches'][side]=matches_bar(bar,ticks);sample['tick_counts'][side]=len(ticks);sample['hashes'][side]=digest(response)
            samples.append(sample)
        basis='bid' if len(samples)==3 and all(s['matches']=={'bid':True,'ask':False} for s in samples) else None
        if basis:add('candle_basis',basis)
        report=CapabilityReport(account_id=account,symbol=name,evidence=tuple(evidence))
        # Metadata values are recorded, not promoted into complete cost/contract policies.
        observed={k:raw[k] for k in ('digits','lotSize','commissionType','preciseTradingCommissionRate','preciseMinCommission','minCommissionType','minCommissionAsset','pnlConversionFeeRate','slDistance','tpDistance','distanceSetIn','tradingMode','leverageId') if k in raw}
        reports[name]={'capability':report.model_dump(mode='json'),'execution_blockers':report.blockers(now(),account,name),'observed_metadata':observed,'candle_samples':samples,'read_only_basis':basis}
    if session.generation!=generation or not session.ready:raise ValueError('audit connection changed')
    return dict(account_id=account,observed_at=at.isoformat(),symbols=reports,orders_enabled=False,qualification_complete=False,evidence_hash=digest(reports))

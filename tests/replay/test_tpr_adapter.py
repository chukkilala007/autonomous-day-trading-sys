import json
from datetime import timedelta
from trading_platform.strategies.tpr1.adapter import TPR,baseline_snapshot
from trading_platform.strategies.tpr1.baseline import from_snapshot
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Bar,Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.values import utc


def synthetic():
    start=utc('2024-01-01T00:00:00Z')
    mids=[100,101,104,102,101,102,103,106,104,105,104,105,108,106,105,106,107,110]
    # Use the original baseline fixture's confirmed trend.
    mids[9]=103
    bars=[]
    for i,v in enumerate(mids):
        bars.append(Bar(instrument='XAUUSD',start=start+timedelta(seconds=i*300),end=start+timedelta(seconds=(i+1)*300),available_at=start+timedelta(seconds=(i+1)*300),basis='bid',open=str(v-.1),high=str(v+.4),low=str(v-.4),close=str(v+.1)))
    born=start+timedelta(seconds=5400)
    for t,o,h,l,c in [(born-timedelta(seconds=60),'110','110.4','109.6','110.1'),(born,'108.6','108.95','108.3','108.9')]:
        bars.append(Bar(instrument='XAUUSD',start=t,end=t+timedelta(seconds=60),available_at=t+timedelta(seconds=60),basis='bid',open=o,high=h,low=l,close=c))
    return Snapshot(cutoff=born+timedelta(seconds=60),bars=tuple(bars))

def instance():
    return Instance.model_validate_json(json.dumps(dict(instance_id='tpr',strategy='tpr1@1',package_digest='test',mode='paper',universe=['XAUUSD'],account=dict(alias='paper',environment='paper'),allocation='0.005')))

def test_adapter_matches_baseline_and_no_unverified_entry():
    s=synthetic();i=instance();p=TPR()
    e=Event(event_id='e',kind='bar',instrument='XAUUSD',source_time=s.cutoff,available_at=s.cutoff)
    out=p.evaluate(i,e,s,(),p.initialize(i))
    assert json.loads(out.decisions[0].diagnostics)==from_snapshot(baseline_snapshot(s,'XAUUSD'),'XAUUSD')
    assert out.decisions[0].outcome=='WATCH'
    assert out.decisions[0].proposal is None
    assert 'EXECUTION_UNVERIFIED' in out.decisions[0].reasons


def executable_snapshot():
    from trading_platform.contracts.events import Quote
    s=synthetic();bars=list(s.bars)
    for period,count in [(900,20),(3600,12)]:
        last=int(s.cutoff.timestamp())//period*period
        for n in range(count):
            end=utc(__import__('datetime').datetime.fromtimestamp(last-n*period,__import__('datetime').timezone.utc))
            bars.append(Bar(instrument='XAUUSD',start=end-timedelta(seconds=period),end=end,available_at=end,basis='bid',open='90',high='91',low='89',close='90'))
    q=Quote(instrument='XAUUSD',bid='108.90',ask='108.91',source_time=s.cutoff,received_at=s.cutoff)
    return Snapshot(cutoff=s.cutoff,bars=tuple(sorted(bars,key=lambda b:b.start)),quotes=(q,))


def test_paper_execution_and_dedup():
    s=executable_snapshot();i=instance();p=TPR()
    metadata=dict(price_basis='bid',tick_size='0.01',actual_session_open=True,session_source_time=s.cutoff.isoformat(),provenance={k:'synthetic-test-fixture' for k in ('price_basis','tick_size','actual_session_open')})
    e=Event(event_id='e',kind='bar',instrument='XAUUSD',source_time=s.cutoff,available_at=s.cutoff,payload=json.dumps({'paper_execution':metadata}))
    out=p.evaluate(i,e,s,(),p.initialize(i));d=out.decisions[0]
    assert d.outcome=='ENTRY', d.reasons
    assert str(d.proposal.entry)=='108.97'  # reference bid plus observed spread
    assert p.evaluate(i,e,s,(),out.state).decisions[0].outcome=='WATCH'
    assert json.loads(d.diagnostics)['current_candidate']['plan']['entry']=='108.96'

import json
from datetime import timedelta
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event,Quote
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.values import utc
from trading_platform.strategies.timer_fixture.adapter import Timer
T=utc('2024-01-01T00:00:00Z')

def test_timer_entry_exit_and_isolation():
    i=Instance.model_validate_json(json.dumps(dict(instance_id='timer',strategy='timer@1',package_digest='x',mode='paper',universe=['TEST'],account=dict(alias='p',environment='paper'),allocation='0.005')))
    q=Quote(instrument='TEST',bid='100',ask='100.01',source_time=T,received_at=T)
    s=Snapshot(cutoff=T,quotes=(q,));e=Event(event_id='timer',kind='timer',instrument='TEST',source_time=T,available_at=T)
    p=Timer();out=p.evaluate(i,e,s,(),p.initialize(i))
    assert out.decisions[0].outcome=='ENTRY' and out.decisions[0].proposal.target is None
    assert p.evaluate(i,e,s,(),out.state).decisions[0].outcome=='NO_ACTION'
    later=T+timedelta(seconds=120)
    pos={'id':'p1','instance':'timer','exit_at':later.isoformat(),'revision':0}
    s=Snapshot(cutoff=later)
    assert p.evaluate(i,e,s,(pos,),out.state).decisions[0].outcome=='MANAGEMENT'
    other=pos|{'instance':'other'}
    assert p.evaluate(i,e,s,(other,),out.state).decisions[0].outcome=='NO_ACTION'

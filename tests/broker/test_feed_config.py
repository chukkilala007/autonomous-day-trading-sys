import json
from datetime import datetime,timezone,timedelta
import pytest
from trading_platform.contracts.config import Instance
from trading_platform.registry.manifest import Manifest
from trading_platform.gateways.ctrader.metadata import CapabilityReport,Evidence
from trading_platform.gateways.ctrader.feed_config import build,validate
from trading_platform.contracts.values import digest
T=datetime(2026,10,17,tzinfo=timezone.utc)


def inputs():
    def instance(name):return Instance(instance_id=name,strategy=name+'@1',package_digest='reviewed',mode='shadow',universe=('X',),account={'alias':'test','environment':'demo','broker_account':'12'},allocation='0.005')
    instances=[instance('arbitrary_a'),instance('arbitrary_b')]
    manifests={i.strategy:Manifest(package=i.strategy,digest='reviewed',entrypoint='unused:Test',subscriptions=('timer',),history=(('M1',10 if n==0 else 30),('H1',4))) for n,i in enumerate(instances)}
    reports={'X':CapabilityReport(account_id='12',symbol='X',evidence=tuple(Evidence(field=k,value=v,source='fixture',observed_at=T-timedelta(minutes=1),valid_until=T+timedelta(hours=1),classification='demo_observed') for k,v in [('candle_basis','bid'),('symbol_id','1')]))}
    return instances,manifests,reports


def test_strategy_independent_union_and_roundtrip():
    config=build(*inputs(),'12',T)
    assert config['requirements']==[['X','bid',1,30],['X','bid',60,4]]
    assert validate(config,'12',T)['symbols']=={'X':1}


@pytest.mark.parametrize('fault',['account','expired','history','manifest','mode','requirements','basis','hash'])
def test_invalid_or_changed_configuration_cannot_start(fault):
    i,m,r=inputs();config=build(i,m,r,'12',T)
    if fault=='account':config['account_id']='13'
    if fault=='basis':config['manifests'][0]['price_basis']='ask'
    if fault=='history':config['manifests'][0]['history']=[]
    if fault=='manifest':config['manifests'][0]['digest']='changed'
    if fault=='mode':config['instances'][0]['mode']='demo'
    if fault=='requirements':config['requirements'][0][3]=1
    if fault!='hash':config['evidence_hash']=digest({k:v for k,v in config.items() if k!='evidence_hash'})
    else:config['evidence_hash']='bad'
    with pytest.raises(ValueError):validate(config,'12',T+timedelta(hours=2) if fault=='expired' else T)


def test_prepare_selects_only_requested_strategy_without_reducing_others(tmp_path,monkeypatch):
    import runpy,sys
    _,_,reports=inputs();now=datetime.now(timezone.utc)
    report=reports['X'].model_copy(update={'evidence':tuple(e.model_copy(update={'observed_at':now-timedelta(seconds=1),'valid_until':now+timedelta(hours=1)}) for e in reports['X'].evidence)})
    probe=tmp_path/'probe.json';probe.write_text(json.dumps({'status':'COLLECTED','account_id':'12','economics':{'account':{'currency':'GBP'}},'capability_audit':{'symbols':{'X':{'capability':report.model_dump(mode='json')}}}}))
    output=tmp_path/'config'
    monkeypatch.setattr(sys,'argv',['prepare_shadow','--probe',str(probe),'--account','12','--symbol','X','--instances','timer_fixture','--destination',str(output)])
    runpy.run_path('scripts/prepare_shadow.py',run_name='__main__')
    feed=json.loads((output/'feed.json').read_text());deployment=json.loads((output/'deployment.json').read_text())
    assert feed['requirements']==[['X','bid',1,1]]
    assert set(deployment['workers'])=={'timer_fixture'}
    assert deployment['instances']==['/analysis/timer_fixture.json']
    assert (output/'tpr1.json').exists()  # Compatible optional Compose mount, not active.

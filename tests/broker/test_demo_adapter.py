import json,runpy
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal
import pytest
from trading_platform.contracts.config import Instance
from trading_platform.contracts.values import canonical
from trading_platform.execution.demo_broker import DemoBroker
from trading_platform.runtime.demo import DemoRuntime
from trading_platform.gateways.ctrader.projection import Projection
from trading_platform.persistence.database import Database
from trading_platform.simulation.replay import load_registry


def test_core_demo_uses_shared_risk_and_preserves_unknown_across_restart(tmp_path):
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    instances=[Instance.model_validate_json(json.dumps(dict(json.loads(i.model_dump_json()),mode='demo',account=dict(json.loads(i.account.model_dump_json()),environment='demo',broker_account='12')))) for i in instances]
    at=rows[0][1].cutoff;sent=[]
    def call(body):
        if body['op']=='acquire': return dict(mode='demo',account_id='12',authorized=True,epoch=1)
        if body['op']=='observe': return dict(mode='demo',account_id='12',observed_at=at.isoformat(),events=[],blockers=[],account={'balance':'10000','equity':'10000','free_margin':'10000','currency':'GBP'})
        if body['op']=='submit': sent.append(body['command']['id']);raise TimeoutError('lost acknowledgement')
        if body['op']=='management_confirmed': return False
        raise AssertionError(body['op'])
    for cycle in range(2):
        broker=DemoBroker('',0,'','12','core',call=call,now=lambda:at)
        with Database(tmp_path/'core') as db:
            runtime=DemoRuntime(db,load_registry('config/registry.json'),instances,broker)
            runtime.process(*rows[0])
            assert len(runtime.status()['active_risk'])==1,runtime.status()
            assert any(c['status']=='UNKNOWN' for c in runtime.status()['orders'])
    assert len(sent)==1
    with Database(tmp_path/'foreign') as db:
        broker.account_id='13'
        with pytest.raises(ValueError): DemoRuntime(db,load_registry('config/registry.json'),instances,broker)


def test_projection_requires_owned_facts_and_known_settlement(tmp_path):
    with Database(tmp_path/'gateway') as db:
        def put(key,value):
            with db.transaction() as c:c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(key,canonical(value)))
        fields=dict(clientOrderId='cmd',symbolId=1,volume=200,tradeSide=1,limitPrice=100)
        put('gateway-send:cmd',dict(instance='a',fields=fields,broker_order_id='1'))
        raw=dict(orderId='1',clientOrderId='cmd',positionId='2',tradeData={'symbolId':'1','volume':'200','tradeSide':'BUY'},limitPrice=100,executedVolume='200',orderStatus='ORDER_STATUS_FILLED')
        put('broker-order:1',dict(owner='a',updated=1000,record=raw))
        pos=dict(owner='a',updated=1000,quantity='2',closed=False,protected=True,record={'price':100,'stopLoss':99})
        put('broker-position:2',pos)
        projection=Projection(db);assert projection.refresh()==[]
        assert projection.events()[-1].kind=='FILLED'
        assert projection.refresh()==[] and len(projection.events())==1
        pos.update(closed=True,updated=2000);put('broker-position:2',pos)
        assert projection.refresh()==['SETTLEMENT_REQUIRED:cmd']
        assert projection.events()[-1].kind=='FILLED'
        settlements={'cmd':{'position_id':'2','complete':True,'evidence_hash':'verified-cost-record','net':'1.25'}}
        assert projection.refresh(settlements)==[]
        assert projection.events()[-1].kind=='CLOSED' and projection.events()[-1].net==Decimal('1.25')
        assert Projection(db).refresh(settlements)==[] and len(projection.events())==2


def test_demo_management_ack_without_confirmation_stays_unknown(tmp_path):
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    from trading_platform.runtime.paper import PaperRuntime
    from trading_platform.simulation.broker import PaperBroker
    from trading_platform.contracts.orders import Management
    from trading_platform.contracts.decisions import Decision
    from datetime import timedelta
    class Delayed(PaperBroker):
        def manage(self,*args): return []
        def management_confirmed(self,id): return False
    with Database(tmp_path/'core') as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,Delayed())
        runtime.process(*rows[0]);command=runtime.executor.command(runtime.status()['orders'][0]['id'])
        original=Decision.model_validate_json(json.dumps(command['body']['decision']));now=rows[0][1].cutoff
        management=Management(target_id=command['id'],owner=command['instance'],revision=command['revision'],action='cancel',expires_at=now+timedelta(seconds=5))
        decision=original.model_copy(update={'outcome':'MANAGEMENT','proposal':management,'event_id':'cancel'})
        mid=runtime.executor.queue_management(decision,now)
        runtime.executor.dispatch(mid,runtime.broker,rows[0][1].quotes[0],now)
        assert runtime.executor.command(mid)['status']=='UNKNOWN'

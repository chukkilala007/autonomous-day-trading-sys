from datetime import datetime,timezone,timedelta
from decimal import Decimal as D
import json
import pytest
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.orders import Fence,DemoTransport,limit_fields
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.events import Quote
from trading_platform.gateways.ctrader.metadata import CapabilityReport,Evidence,REQUIRED
T=datetime(2026,1,1,tzinfo=timezone.utc)


def fixture():
    entry=Entry(instrument='X',side='buy',order_type='limit',entry='99',worst_fill='99',stop='98',target='101',expires_at=T+timedelta(seconds=30))
    quote=Quote(instrument='X',bid='100',ask='100.01',source_time=T,received_at=T)
    values={f:'verified' for f in REQUIRED};values.update(account_type='HEDGED',symbol_id='1',tick_grid='0.01',volume_grid=json.dumps({'min':'1','max':'100','step':'1'}),session_state='OPEN',expiry='GOOD_TILL_DATE',order_types='["limit"]')
    report=CapabilityReport(account_id='12',symbol='X',evidence=tuple(Evidence(field=k,value=v,source='synthetic-transport-test',classification='broker_verified',observed_at=T,valid_until=T+timedelta(seconds=10)) for k,v in values.items()))
    command={'id':'synthetic-command','instance':'a','body':{'decision':{'environment':'demo','proposal':json.loads(entry.model_dump_json())},'size':{'quantity':'2'}}}
    return command,report,quote


def test_fences_persist_and_stale_send_rejected(tmp_path):
    class Session: account_id=12;ready=True
    with Database(tmp_path/'db') as db:
        gateway=DemoTransport(db,Session(),authorized=True);a=gateway.fence.acquire('a');b=gateway.fence.acquire('b')
        command,report,quote=fixture()
        with pytest.raises(ValueError,match='stale core'): gateway.prepare(command,'a',a,report,quote,T,T)
        fields=gateway.prepare(command,'b',b,report,quote,T,T)
        assert fields['volume']==200 and fields['limitPrice']==99 and fields['ctidTraderAccountId']==12
        with pytest.raises(ValueError): gateway.prepare(command,'b',b,report,quote,T+timedelta(seconds=11),T)
    with Database(tmp_path/'db') as db:
        Fence(db,12).check('b',b)


def test_demo_transport_persists_uncertainty_and_never_retries(tmp_path):
    pytest.importorskip('ctrader_open_api')
    class Client:
        calls=0
        def send(self,*args,**kw): self.calls+=1;raise TimeoutError('accepted, ack lost')
    class Session: account_id=12;ready=True;client=Client()
    with Database(tmp_path/'db') as db:
        gateway=DemoTransport(db,Session());epoch=gateway.fence.acquire('a');command,report,quote=fixture()
        with pytest.raises(ValueError,match='authorization'): gateway.send(command,'a',epoch,report,quote,T,T)
        gateway.authorized=True
        with pytest.raises(TimeoutError): gateway.send(command,'a',epoch,report,quote,T,T)
        with pytest.raises(ValueError,match='already attempted'): gateway.send(command,'a',epoch,report,quote,T,T)
        assert gateway.session.client.calls==1


def test_netted_account_cannot_merge_strategy_ownership(tmp_path):
    class Session: account_id=12;ready=True
    with Database(tmp_path/'db') as db:
        gateway=DemoTransport(db,Session(),authorized=True);epoch=gateway.fence.acquire('core')
        command,report,quote=fixture()
        report=report.model_copy(update={'evidence':tuple(e.model_copy(update={'value':'NETTED'}) if e.field=='account_type' else e for e in report.evidence)})
        with pytest.raises(ValueError,match='netted ownership'): gateway.prepare(command,'core',epoch,report,quote,T,T)

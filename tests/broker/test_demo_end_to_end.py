"""Offline protocol fixtures only: no socket or actual broker credentials."""
import json,runpy
from pathlib import Path
from datetime import timedelta
from decimal import Decimal as D
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from google.protobuf.json_format import ParseDict
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage
from trading_platform.contracts.config import Instance
from trading_platform.contracts.decisions import Decision
from trading_platform.persistence.database import Database
from trading_platform.market_data.service import Feed
from trading_platform.risk.sizing import Contract
from trading_platform.execution.outbox import Executor
from trading_platform.execution.demo_broker import DemoBroker
from trading_platform.gateways.ctrader.orders import DemoTransport
from trading_platform.gateways.ctrader.execution import ExecutionLedger
from trading_platform.gateways.ctrader.demo_api import DemoAPI


def test_protocol_accept_fill_close_releases_shared_risk_only_after_settlement(tmp_path):
    fixture=runpy.run_path('tests/broker/test_demo_transport.py');command,report,quote=fixture['fixture']();now=fixture['T']
    contract=Contract(instrument='X',account_currency='GBP',valuation_currency='GBP',quote_to_account='1',contract_value_per_unit='1',commission_per_unit='0',slippage_per_unit='0',minimum='1',maximum='100',step='1',tick='.01',margin_per_unit='1',verified_at=now,provenance='offline-protocol-fixture')
    data=json.loads(Path('config/instances/tpr1.json').read_text());data.update(mode='demo',universe=['X']);data['account'].update(environment='demo',broker_account='12')
    instance=Instance.model_validate_json(json.dumps(data))
    decision=Decision(instance=instance.instance_id,account=instance.account.alias,environment='demo',package=instance.strategy,config_hash=instance.hash,event_id='offline',snapshot_hash='offline-snapshot',at=now,outcome='ENTRY',proposal=command['body']['decision']['proposal'])
    raw={};calls=[]
    class Client:
        def send(self,request,**kwargs):
            calls.append(request.DESCRIPTOR.name)
            raw.update(ctidTraderAccountId='12',executionType='ORDER_ACCEPTED',order=dict(orderId='1',clientOrderId=request.clientOrderId,tradeData=dict(symbolId=str(request.symbolId),volume=str(request.volume),tradeSide='BUY'),orderType='LIMIT',orderStatus='ORDER_STATUS_ACCEPTED',limitPrice=request.limitPrice,executedVolume='0',utcLastUpdateTimestamp=str(int(now.timestamp()*1000))))
            event=ParseDict(raw,ProtoOAExecutionEvent())
            return succeed(ProtoMessage(payloadType=event.payloadType,payload=event.SerializeToString()))
    class Session: account_id=12;ready=True;client=Client()
    with Database(tmp_path/'gateway') as gdb,Database(tmp_path/'core') as db:
        feed=Feed(gdb);feed.ingest_quote(quote)
        ledger=ExecutionLedger(gdb,12);gateway=DemoTransport(gdb,Session(),authorized=True)
        value=dict(mode='demo',account_id='12',observed_at=now.isoformat(),classification='broker_verified',evidence_hash='offline-only',history_complete=True,external_exposure=False,account={'balance':'10000','equity':'10000','free_margin':'10000','currency':'GBP'},contracts={'X':json.loads(contract.model_dump_json())},settlements={})
        api=DemoAPI(gateway,ledger,feed,{'X':report},lambda:value,lambda:now)
        def call(body):
            results=[];errors=[];api.handle(body).addCallbacks(results.append,errors.append)
            if errors: errors[0].raiseException()
            assert results,'fixture must complete synchronously'
            return results[0]
        broker=DemoBroker('',0,'','12','core',call=call,now=lambda:now)
        executor=Executor(db,instance.account);executor.book.limits.observe(now,D('10000'))
        cid=executor.enqueue(decision,instance,quote,contract,now,D('10000'),D('10000'),D('10000'),'X')
        executor.dispatch(cid,broker,quote,now)
        assert executor.command(cid)['status']=='ACCEPTED'
        volume=raw['order']['tradeData']['volume']
        raw['executionType']='ORDER_FILLED';raw['order'].update(orderStatus='ORDER_STATUS_FILLED',executedVolume=volume,positionId='2',utcLastUpdateTimestamp=str(int(now.timestamp()*1000)+1))
        raw['position']=dict(positionId='2',tradeData=raw['order']['tradeData'],positionStatus='POSITION_STATUS_OPEN',swap='0',price=99,stopLoss=98,takeProfit=101,utcLastUpdateTimestamp=str(int(now.timestamp()*1000)+1))
        ledger.apply(raw);assert executor.reconcile(broker)
        assert db.connection.execute('SELECT count(*) FROM positions').fetchone()[0]==1
        raw['position'].update(positionStatus='POSITION_STATUS_CLOSED',utcLastUpdateTimestamp=str(int(now.timestamp()*1000)+2))
        ledger.apply(raw);assert not executor.reconcile(broker)
        assert db.connection.execute("SELECT count(*) FROM reservations WHERE status!='RELEASED'").fetchone()[0]==1
        value['settlements'][cid]=dict(position_id='2',complete=True,evidence_hash='offline-settlement',net='1.25')
        assert executor.reconcile(broker)
        assert executor.command(cid)['status']=='CLOSED'
        assert not db.connection.execute('SELECT 1 FROM positions').fetchone()
        assert not db.connection.execute("SELECT 1 FROM reservations WHERE status!='RELEASED'").fetchone()
        assert calls==['ProtoOANewOrderReq']
        assert executor.reconcile(broker) and calls==['ProtoOANewOrderReq']
        # Stale epochs and disabled authorization never reach the transport.
        gateway.fence.acquire('replacement')
        with pytest.raises(ValueError): broker.observe()
        gateway.authorized=False
        with pytest.raises(ValueError): DemoBroker('',0,'','12','new',call=call,now=lambda:now)

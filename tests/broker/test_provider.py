import copy,json,runpy
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.provider import Provider,latest_orders

T=datetime(2026,10,16,tzinfo=timezone.utc)


def test_external_account_exposure_cannot_be_allocated_to_strategies(tmp_path):
    with Database(tmp_path/'db') as db:
        session=SimpleNamespace(account_id=12,generation=1,ready=True)
        provider=Provider(session,db,lambda:{},lambda:None,lambda:T)
        provider.economics=SimpleNamespace(collect=lambda:succeed(dict(account_id='12',observed_at=T.isoformat(),account=dict(balance='100',equity='100',free_margin='50',currency='GBP'),reconciliation=dict(position=[dict(positionId='1')],order=[]))))
        results=[];provider.reconcile().addCallback(results.append)
        assert json.loads(results[0]['valuation'])['external_exposure'] is True
        assert not results[0]['execution_events']


def test_equal_revision_conflict_is_never_silently_overwritten():
    a=dict(orderId='1',utcLastUpdateTimestamp='1',orderStatus='A')
    with pytest.raises(ValueError): latest_orders([a,dict(a,orderStatus='B')])
    assert latest_orders([dict(a,utcLastUpdateTimestamp='2'),a])['1']['utcLastUpdateTimestamp']=='2'


def test_closed_deals_recover_missing_position_without_inventing_settlement(tmp_path):
    from trading_platform.contracts.values import canonical
    policy,deals=runpy.run_path('tests/broker/test_settlement_mapping.py')['fixture']()
    fields=dict(clientOrderId='cmd',symbolId=1,volume=200,tradeSide=1,limitPrice=99)
    order=dict(orderId='3',clientOrderId='cmd',positionId='2',tradeData=dict(symbolId='1',volume='200',tradeSide='BUY'),limitPrice=99,executedVolume='200',utcLastUpdateTimestamp=str(int(T.timestamp()*1000)),orderStatus='ORDER_STATUS_FILLED')
    deals[0]['executionPrice']=99
    with Database(tmp_path/'db') as db:
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:cmd',canonical(dict(fields=fields,at=T-timedelta(days=1),instance='x',status='UNKNOWN'))))
        session=SimpleNamespace(account_id=12,generation=1,ready=True)
        def read(name,**kwargs): return succeed(dict(ctidTraderAccountId='12',hasMore=False,**({'order':[order]} if name=='ProtoOAOrderListReq' else {'deal':copy.deepcopy(deals)})))
        session.read=read
        provider=Provider(session,db,lambda:{},lambda:policy,lambda:T)
        provider.economics=SimpleNamespace(collect=lambda:succeed(dict(observed_at=T.isoformat(),account=dict(balance='100',equity='100',free_margin='100',currency='GBP'),reconciliation=dict(position=[],order=[]))))
        results=[];errors=[];provider.reconcile(reconnect=True).addCallbacks(results.append,errors.append)
        assert not errors,errors
        value=json.loads(results[0]['valuation']);assert value['settlements'][0]['closed']=='2'
        assert results[0]['execution_events'][0]['position']['positionStatus']=='POSITION_STATUS_CLOSED'
        complete=results[0]
        with pytest.raises(ValueError): provider.checkpoint(complete)
        # Missing opening deal must halt, even though the broker position is absent.
        deals.pop(0);results=[];errors=[]
        provider.reconcile().addCallbacks(results.append,errors.append)
        assert errors and not results

        from trading_platform.gateways.ctrader.execution import ExecutionLedger
        ledger=ExecutionLedger(db,12)
        for event in complete['execution_events']: ledger.apply(event)
        provider.checkpoint(complete)
        session.read=lambda *a,**k: (_ for _ in ()).throw(AssertionError('unexpected history re-fetch'))
        results=[];errors=[];provider.reconcile(reconnect=True).addCallbacks(results.append,errors.append)
        assert results and not errors
        assert json.loads(results[0]['valuation'])['settlements'][0]['command_id']=='cmd'


def test_verified_closure_resolves_equal_revision_created_event(tmp_path):
    from trading_platform.gateways.ctrader.execution import ExecutionLedger
    from trading_platform.contracts.values import canonical
    fields=dict(clientOrderId='cmd',symbolId=1,volume=100,tradeSide=1,limitPrice=99,stopLoss=90,takeProfit=110)
    order=dict(orderId='3',clientOrderId='cmd',positionId='2',tradeData=dict(symbolId='1',volume='100',tradeSide='BUY'),limitPrice=99,executedVolume='100',utcLastUpdateTimestamp='1000',orderStatus='ORDER_STATUS_FILLED')
    position=dict(positionId='2',positionStatus='POSITION_STATUS_CREATED',tradeData=dict(symbolId='1',volume='0',tradeSide='BUY'),price='99',utcLastUpdateTimestamp='2000')
    with Database(tmp_path/'db') as db:
        db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:cmd',canonical(dict(fields=fields,at=T,instance='x',status='OBSERVED'))))
        ledger=ExecutionLedger(db,12);ledger.apply(dict(ctidTraderAccountId='12',order=order,position=position))
        read=lambda:json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:2'").fetchone()[0])
        closed=dict(position,positionStatus='POSITION_STATUS_CLOSED')
        ledger.apply(dict(ctidTraderAccountId='12',order=order,position=closed))
        assert read()['closed'] is False
        ledger.apply(dict(ctidTraderAccountId='12',order=order,position=closed,settlement_evidence_hash='a'*64))
        assert read()['closed'] is True and read()['quantity']=='0'

import copy,json,runpy
from datetime import datetime,timezone
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
        with db.transaction() as c: c.execute('INSERT INTO checkpoints VALUES (?,?)',('gateway-send:cmd',canonical(dict(fields=fields,at=T.replace(hour=0)-__import__('datetime').timedelta(days=1),instance='x',status='UNKNOWN'))))
        session=SimpleNamespace(account_id=12,generation=1,ready=True)
        def read(name,**kwargs): return succeed(dict(ctidTraderAccountId='12',hasMore=False,**({'order':[order]} if name=='ProtoOAOrderListReq' else {'deal':copy.deepcopy(deals)})))
        session.read=read
        provider=Provider(session,db,lambda:{},lambda:policy,lambda:T)
        provider.economics=SimpleNamespace(collect=lambda:succeed(dict(observed_at=T.isoformat(),account=dict(balance='100',equity='100',free_margin='100',currency='GBP'),reconciliation=dict(position=[],order=[]))))
        results=[];errors=[];provider.reconcile(reconnect=True).addCallbacks(results.append,errors.append)
        assert not errors,errors
        value=json.loads(results[0]['valuation']);assert value['settlements'][0]['closed']=='2'
        assert results[0]['execution_events'][0]['position']['positionStatus']=='POSITION_STATUS_CLOSED'
        # Missing opening deal must halt, even though the broker position is absent.
        deals.pop(0);results=[];errors=[]
        provider.reconcile().addCallbacks(results.append,errors.append)
        assert errors and not results

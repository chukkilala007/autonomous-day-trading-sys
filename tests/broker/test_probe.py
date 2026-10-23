import copy,runpy
from types import SimpleNamespace
from datetime import datetime,timezone
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from trading_platform.gateways.ctrader.probe import discover,collect


def test_discovery_refreshes_private_tokens_and_filters_live():
    sent=[];rotations=[]
    old=dict(client_id='synthetic-id',client_secret='synthetic-secret',access_token='old',refresh_token='refresh',expires_at=0)
    store=SimpleNamespace(read=lambda:old,rotate=lambda prior,response,now:(rotations.append(True) or dict(old,access_token='new',expires_at=999)))
    def wire(name,**fields):
        sent.append((name,fields))
        if name=='ProtoOAGetAccountListByAccessTokenReq': return succeed({'ctidTraderAccount':[{'ctidTraderAccountId':'1','isLive':True},{'ctidTraderAccountId':'2','isLive':False},{'ctidTraderAccountId':'3'}]})
        return succeed({})
    values=[];discover(wire,store,lambda:1).addCallback(values.append)
    assert rotations==[True] and values==[[{'ctidTraderAccountId':'2','isLive':False}]]
    assert sent[-1][1]['accessToken']=='new'
    assert [x[0] for x in sent]==['ProtoOAApplicationAuthReq','ProtoOARefreshTokenReq','ProtoOAGetAccountListByAccessTokenReq']


def test_probe_collects_only_read_requests_without_claiming_qualification():
    trader,rec,pnl,assets=runpy.run_path('tests/broker/test_economics.py')['fixture']()
    session=SimpleNamespace(account_id=12,generation=1,ready=True,demo_binding=dict(account_id='12',generation=1,is_live=False));sent=[]
    def read(name,**fields):
        sent.append(name)
        values={'ProtoOASymbolsListReq':dict(ctidTraderAccountId='12',symbol=[dict(symbolId='1',symbolName='EURUSD')]),
            'ProtoOASymbolByIdReq':dict(ctidTraderAccountId='12',symbol=[dict(symbolId='1')]),
            'ProtoOAGetTrendbarsReq':dict(ctidTraderAccountId='12',trendbar=[],hasMore=False),
            'ProtoOATraderReq':trader,'ProtoOAReconcileReq':rec,'ProtoOAGetPositionUnrealizedPnLReq':pnl,'ProtoOAAssetListReq':assets}
        return succeed(copy.deepcopy(values[name]))
    session.read=read;results=[]
    collect(session,lambda:datetime(2026,10,16,tzinfo=timezone.utc),['EURUSD']).addCallback(results.append)
    assert results and not results[0]['orders_enabled'] and not results[0]['qualification_complete']
    from trading_platform.gateways.ctrader.client import READ_REQUESTS
    assert set(sent)<=READ_REQUESTS

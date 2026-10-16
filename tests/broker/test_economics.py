import copy
from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from trading_platform.gateways.ctrader.economics import account_money,EconomicsCollector


def fixture():
    trader=dict(ctidTraderAccountId='12',trader=dict(ctidTraderAccountId='12',balance='1000000',moneyDigits=2,depositAssetId='1',accountType='HEDGED',totalMarginCalculationType='SUM',balanceVersion='3'))
    rec=dict(ctidTraderAccountId='12',position=[dict(positionId='2',positionStatus='POSITION_STATUS_OPEN',usedMargin='2500',moneyDigits=2)],order=[])
    pnl=dict(ctidTraderAccountId='12',moneyDigits=2,positionUnrealizedPnL=[dict(positionId='2',netUnrealizedPnL='-1234')])
    assets=dict(ctidTraderAccountId='12',asset=[dict(assetId='1',name='GBP')])
    return trader,rec,pnl,assets


def test_account_currency_server_pnl_and_scaled_margin():
    assert account_money('12',*fixture())==dict(currency='GBP',balance='10000',equity='9987.66',free_margin='9962.66')


@pytest.mark.parametrize('fault',['foreign','netted','margin','bonus','missing_pnl','duplicate','scale','currency'])
def test_unknown_economics_rejected(fault):
    trader,rec,pnl,assets=fixture()
    if fault=='foreign': pnl['ctidTraderAccountId']='99'
    if fault=='netted': trader['trader']['accountType']='NETTED'
    if fault=='margin': trader['trader']['totalMarginCalculationType']='NET'
    if fault=='bonus': trader['trader']['managerBonus']='1'
    if fault=='missing_pnl': pnl['positionUnrealizedPnL']=[]
    if fault=='duplicate': rec['position']*=2
    if fault=='scale': del rec['position'][0]['moneyDigits']
    if fault=='currency': assets['asset'][0]['name']='BITCOIN'
    with pytest.raises(ValueError): account_money('12',trader,rec,pnl,assets)


@pytest.mark.parametrize('race',['none','generation','balance','timeout'])
def test_collection_brackets_mutable_account_and_never_uses_new_receipt_as_freshness(race):
    trader,rec,pnl,assets=fixture();at=datetime(2026,10,16,tzinfo=timezone.utc);clock=[at];count=[0]
    session=SimpleNamespace(account_id=12,ready=True,generation=1)
    def read(name):
        count[0]+=1
        value=copy.deepcopy({'ProtoOATraderReq':trader,'ProtoOAReconcileReq':rec,'ProtoOAGetPositionUnrealizedPnLReq':pnl,'ProtoOAAssetListReq':assets}[name])
        if count[0]==5:
            if race=='generation': session.generation+=1
            if race=='balance': value['trader']['balanceVersion']='4'
            if race=='timeout': clock[0]+=timedelta(seconds=3)
        return succeed(value)
    session.read=read;values=[];errors=[]
    EconomicsCollector(session,lambda:clock[0]).collect().addCallbacks(values.append,errors.append)
    assert bool(values)==(race=='none')
    assert bool(errors)==(race!='none')


def test_max_margin_groups_direction_totals_per_symbol_not_individual_positions():
    trader,rec,pnl,assets=fixture();trader['trader']['totalMarginCalculationType']='MAX'
    rec['position']=[];pnl['positionUnrealizedPnL']=[]
    for i,(symbol,side,amount) in enumerate([(1,'BUY',1000),(1,'BUY',2000),(1,'SELL',2500),(2,'SELL',4000),(2,'BUY',1000)]):
        rec['position'].append(dict(positionId=str(i),positionStatus='POSITION_STATUS_OPEN',usedMargin=str(amount),moneyDigits=2,tradeData=dict(symbolId=str(symbol),tradeSide=side)))
        pnl['positionUnrealizedPnL'].append(dict(positionId=str(i),netUnrealizedPnL='0'))
    assert account_money('12',trader,rec,pnl,assets)['free_margin']=='9930'
    rec['position'][0]['tradeData']['tradeSide']='UNKNOWN'
    with pytest.raises(ValueError):account_money('12',trader,rec,pnl,assets)


def test_max_margin_empty_account():
    trader,rec,pnl,assets=fixture();trader['trader']['totalMarginCalculationType']='MAX'
    rec['position']=[];pnl['positionUnrealizedPnL']=[]
    assert account_money('12',trader,rec,pnl,assets)['free_margin']=='10000'

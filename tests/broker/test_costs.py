from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from trading_platform.gateways.ctrader.costs import commission, conversion, expected_margin

NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)

@pytest.mark.parametrize('kind,rate,expected', [('USD_PER_MILLION_USD',3500000000,'3.85'),('USD_PER_LOT',350000000,'3.5'),('QUOTE_CCY_PER_LOT',350000000,'3.5'),('PERCENTAGE_OF_VALUE',100,'1.1')])
def test_precise_commission(kind,rate,expected):
    metadata=dict(commissionType=kind,preciseTradingCommissionRate=rate,lotSize=10000000,preciseMinCommission=0,minCommissionType='QUOTE_CURRENCY')
    args=dict(quantity='100000',price='1.1',quote_currency='USD',account_currency='USD',account='demo',now=NOW,paths={})
    assert commission(metadata,**args)==Decimal(expected)
    metadata['preciseMinCommission']=500000000
    assert commission(metadata,**args)==5
    del metadata['preciseTradingCommissionRate']
    with pytest.raises(KeyError):commission(metadata,**args)


def test_cost_conversion_uses_upper_bound_and_rejects_bad_evidence():
    quote=dict(base='EUR',quote='USD',bid='1.1',ask='1.2',account='demo',observed_at=NOW)
    def convert(source,target,quotes):return conversion('110',source,target,quotes,account='demo',now=NOW)
    assert convert('EUR','USD',[quote])==132
    assert convert('USD','EUR',[quote])==100
    for patch in ({'account':'foreign'},{'observed_at':NOW-timedelta(seconds=3)},{'observed_at':NOW+timedelta(seconds=1)},{'bid':'1.3'},{'bid':'NaN'}):
        with pytest.raises(ValueError):convert('EUR','USD',[quote|patch])
    with pytest.raises(ValueError):convert('EUR','EUR',[quote,quote])
    with pytest.raises(ValueError):convert('EUR','GBP',[quote])


def test_margin_is_quantity_specific_bound_and_fresh():
    request=dict(ctidTraderAccountId=7,symbolId=2,volume=[100,200])
    response=dict(ctidTraderAccountId=7,moneyDigits=2,margin=[dict(volume=100,buyMargin=123,sellMargin=145),dict(volume=200,buyMargin=300,sellMargin=400)])
    args=dict(request=request,account=7,symbol_id=2,volume=200,side='BUY',observed_at=NOW,now=NOW)
    assert expected_margin(response,**args)==3
    for patch in ({'volume':300},{'symbol_id':3},{'account':8},{'side':'UNKNOWN'},{'observed_at':NOW-timedelta(seconds=3)}):
        with pytest.raises(ValueError):expected_margin(response,**(args|patch))
    with pytest.raises(ValueError):expected_margin(response|{'margin':response['margin']*2},**args)

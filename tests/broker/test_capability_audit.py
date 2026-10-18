import copy
import pytest
pytest.importorskip('ctrader_open_api')
from trading_platform.gateways.ctrader.audit import decode_ticks,matches_bar


def fixture():
    return dict(ctidTraderAccountId='12',hasMore=False,tickData=[dict(timestamp='59999',tick='105'),dict(timestamp='-10000',tick='-5'),dict(timestamp='-49000',tick='2')])


def test_tick_delta_prices_and_chronology_match_exact_ohlc():
    ticks=decode_ticks(fixture(),'12',0,59999)
    assert ticks==[(999,102),(49999,100),(59999,105)]
    assert matches_bar(dict(low='100',deltaOpen='2',deltaHigh='5',deltaClose='5'),ticks)
    assert not matches_bar(dict(low='101',deltaOpen='2',deltaHigh='5',deltaClose='5'),ticks)


@pytest.mark.parametrize('fault',['foreign','more','empty','chronology','range','price'])
def test_tick_audit_rejects_unproven_samples(fault):
    raw=fixture()
    if fault=='foreign':raw['ctidTraderAccountId']='13'
    if fault=='more':raw['hasMore']=True
    if fault=='empty':raw['tickData']=[]
    if fault=='chronology':raw['tickData'][1]['timestamp']='1'
    if fault=='range':raw['tickData'][0]['timestamp']='60000'
    if fault=='price':raw['tickData'][0]['tick']='0'
    with pytest.raises(ValueError):decode_ticks(raw,'12',0,59999)


def test_audit_distinguishes_observed_basis_from_execution_qualification():
    from datetime import datetime,timezone,timedelta
    from types import SimpleNamespace
    from twisted.internet.defer import succeed
    from trading_platform.gateways.ctrader.audit import collect
    at=datetime(2026,10,16,tzinfo=timezone.utc)
    starts=[int(at.timestamp()*1000)-n*60000 for n in (3,2,1)]
    probe={'account_id':'12','symbols':{'X':1},'metadata':{'symbol':[dict(symbolId='1',minVolume='100',maxVolume='1000',stepVolume='100',digits=5)]},'economics':{'trader':{'accountType':'HEDGED'}},'trendbars':{'X':[dict(utcTimestampInMinutes=str(s//60000),low='100',deltaOpen='0',deltaHigh='0',deltaClose='0') for s in starts]}}
    def read(name,**fields):
        assert name=='ProtoOAGetTickDataReq'
        return succeed(dict(ctidTraderAccountId='12',hasMore=False,tickData=[dict(timestamp=str(fields['fromTimestamp']+60000),tick='100' if fields['type']==1 else '101')]))
    session=SimpleNamespace(account_id=12,generation=1,ready=True,read=read);values=[]
    collect(session,probe,lambda:at).addCallback(values.append)
    result=values[0]['symbols']['X']
    assert result['read_only_basis']=='bid'
    assert 'candle_basis' not in result['execution_blockers']
    assert {'tick_grid','commission','margin','session_state'}<=set(result['execution_blockers'])
    assert not values[0]['qualification_complete'] and not values[0]['orders_enabled']


def test_quote_open_preserves_observed_unchanged_side():
    from trading_platform.gateways.ctrader.audit import quote_ohlc
    sides={'bid':[(59000,100),(62000,99),(65000,101)],'ask':[(59500,103),(61000,104),(64000,105)]}
    assert quote_ohlc(sides,60000,65999)=={'bid':[100,101,99,101],'ask':[104,105,104,105]}
    with pytest.raises(ValueError,match='preceding'):quote_ohlc({'bid':[(62000,99)],'ask':sides['ask']},60000,65999)
    with pytest.raises(ValueError,match='ambiguous'):quote_ohlc({'bid':[(59000,100),(59000,101)],'ask':sides['ask']},60000,65999)

from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed
from trading_platform.gateways.ctrader.gap_audit import collect

T = datetime(2026, 10, 20, tzinfo=timezone.utc)


@pytest.mark.parametrize('case', ['empty', 'ticks', 'bar', 'foreign', 'incomplete', 'reconnect'])
def test_gap_diagnosis_does_not_manufacture_history(case):
    calls = []
    def read(name, **fields):
        calls.append(name)
        result = dict(ctidTraderAccountId='12', hasMore=False)
        if name == 'ProtoOAGetTrendbarsReq':
            del result['hasMore']  # absent from the pinned SDK trendbar response
            result['trendbar'] = [dict(utcTimestampInMinutes=str(int(T.timestamp())//60))] if case=='bar' else []
        else:
            result['tickData'] = [dict(timestamp=str(int(T.timestamp()*1000)), tick='100000')] if case=='ticks' else []
            if case=='foreign': result['ctidTraderAccountId']='13'
            if case=='incomplete': result['hasMore']=True
            if case=='reconnect': session.generation+=1
        return succeed(result)
    session=SimpleNamespace(account_id=12,generation=1,ready=True,read=read)
    values=[];errors=[]
    collect(session,1,T,lambda:T+timedelta(minutes=2)).addCallback(values.append).addErrback(errors.append)
    if case in ('foreign','incomplete','reconnect'):
        assert errors and not values
    else:
        assert not errors
        assert values[0]['status']=={'empty':'NO_TICKS_REPORTED','ticks':'TICKS_WITHOUT_BAR','bar':'BAR_PRESENT'}[case]
        assert values[0]['repaired'] is False and values[0]['orders_enabled'] is False
    assert set(calls)<= {'ProtoOAGetTrendbarsReq','ProtoOAGetTickDataReq'}

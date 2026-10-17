import runpy
from datetime import timedelta
import pytest
pytest.importorskip('twisted')
from twisted.internet.defer import succeed,Deferred
from trading_platform.gateways.ctrader.margin_quote import MarginQuote


def fixture():
    policy,entry,args=runpy.run_path('tests/broker/test_contract_builder.py')['fixture']()
    clock=[args['now']];revision=[0];calls=[]
    class Session:
        account_id=12;ready=True;generation=1
        def read(self,name,**fields):
            calls.append((name,fields))
            raw=args['margin_response']
            return succeed(dict(raw,ctidTraderAccountId='12',margin=[{k:str(v) for k,v in row.items()} for row in raw['margin']]))
    session=Session()
    conversion=dict(account_id='12',currency='GBP',source_currency='USD',instrument='X',rate='.8',observed_at=clock[0],evidence_hash='b'*64)
    collector=MarginQuote(session,lambda symbol:policy,lambda symbol:conversion,lambda entry:[100,500,1000],lambda:revision[0],lambda:clock[0])
    return collector,entry,session,clock,revision,calls,conversion


def result(deferred):
    values=[];errors=[];deferred.addCallbacks(values.append,errors.append)
    if errors:errors[0].raiseException()
    assert values
    return values[0]


def test_correlated_read_cache_and_revision_invalidation():
    collector,entry,session,clock,revision,calls,conversion=fixture()
    first=result(collector(entry));assert result(collector(entry))==first and len(calls)==1
    assert calls[0][0]=='ProtoOAExpectedMarginReq'
    assert 'ctidTraderAccountId' not in calls[0][1]
    revision[0]+=1
    result(collector(entry));assert len(calls)==2
    session.generation+=1
    result(collector(entry));assert len(calls)==3
    clock[0]+=timedelta(seconds=3)
    with pytest.raises(ValueError,match='stale conversion'):result(collector(entry))
    assert len(calls)==3


@pytest.mark.parametrize('change',['reconnect','exposure','disconnect','timeout'])
def test_inflight_races_never_publish_cost_evidence(change):
    collector,entry,session,clock,revision,calls,conversion=fixture()
    pending=Deferred();session.read=lambda *a,**kw:pending
    outcome=collector(entry)
    if change=='reconnect':session.generation+=1
    elif change=='exposure':revision[0]+=1
    elif change=='disconnect':session.ready=False
    else:clock[0]+=timedelta(seconds=3)
    args=runpy.run_path('tests/broker/test_contract_builder.py')['fixture']()[2]
    pending.callback(args['margin_response'])
    with pytest.raises(ValueError):result(outcome)
    assert not collector.cache


@pytest.mark.parametrize('patch',[{'account_id':'13'},{'currency':'EUR'},{'source_currency':'EUR'},{'instrument':'Y'}])
def test_foreign_conversion_rejected_before_request(patch):
    collector,entry,session,clock,revision,calls,conversion=fixture()
    conversion.update(patch)
    with pytest.raises(ValueError,match='foreign conversion'):result(collector(entry))
    assert calls==[]

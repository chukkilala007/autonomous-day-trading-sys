import pytest
from trading_platform.contracts.orders import Entry, Management
from trading_platform.contracts.decisions import Decision
from trading_platform.contracts.values import utc

T='2024-01-01T00:00:00Z'
END='2024-01-01T01:00:00Z'

def entry(**kw):
    data=dict(instrument='X',side='buy',order_type='market',worst_fill='100',stop='99',exit_at=END,expires_at=END)
    return Entry(**(data|kw))

def test_generic_market_timed_exit_without_target():
    assert entry().target is None
    with pytest.raises(ValueError): entry(order_type='stop')
    with pytest.raises(ValueError): entry(stop='101')

def test_decision_action_and_ownership():
    data=dict(instance='a',account='paper',environment='paper',package='test@1',config_hash='h',event_id='e',snapshot_hash='s',at=T,outcome='ENTRY')
    with pytest.raises(ValueError): Decision(**data)
    d=Decision(**data,proposal=entry())
    assert Decision.model_validate_json(d.model_dump_json()).id==d.id
    m=Management(target_id='p',owner='b',revision=0,action='close',expires_at=END)
    with pytest.raises(ValueError): Decision(**(data|{'outcome':'MANAGEMENT'}),proposal=m)
    with pytest.raises(ValueError): m.authorize('b','b',1,utc(T))
    with pytest.raises(ValueError): m.authorize('b','b',0,utc(END))

import pytest
from trading_platform.contracts.events import Event
from trading_platform.contracts.values import utc
from trading_platform.runtime.scheduler import Scheduler,asof
from trading_platform.simulation.clock import Clock
T='2024-01-01T00:00:00Z';L='2024-01-01T00:01:00Z'

def event(i='a',at=T): return Event(event_id=i,kind='timer',source_time=T,available_at=at,instrument='X')

def test_causality_and_clock():
    s=asof(utc(T),features=(event(at=L),))
    assert not s.features
    c=Clock(T);c.advance(L)
    with pytest.raises(ValueError): c.advance(T)

def test_overflow_isolated_and_future_waits():
    q=Scheduler(1);q.register('a');q.register('b')
    q.enqueue('a',event())
    with pytest.raises(ValueError): q.enqueue('a',event('b'))
    with pytest.raises(ValueError): q.pop('a',utc(L))
    q.enqueue('b',event(at=L));assert q.pop('b',utc(T)) is None
    assert q.pop('b',utc(L)).event_id=='a'

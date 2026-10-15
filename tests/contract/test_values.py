from datetime import datetime
from decimal import Decimal
import pytest
from hypothesis import given, strategies as st
from trading_platform.contracts.values import Money, canonical, digest
from trading_platform.contracts.events import Quote, Event, Bar
from trading_platform.contracts.snapshots import Snapshot

T='2024-01-01T00:00:00Z'

def test_exact_roundtrip_and_frozen():
    m=Money(amount='1.1000000000000000001',currency='GBP')
    assert Money.model_validate_json(m.model_dump_json()) == m
    assert digest(m)==digest(Money(amount=m.amount,currency='GBP'))
    with pytest.raises(Exception): m.amount=Decimal('2')

@pytest.mark.parametrize('x',['NaN','Infinity',1.1,True])
def test_invalid_number(x):
    with pytest.raises(ValueError): Money(amount=x,currency='GBP')

@given(st.integers(min_value=-100000,max_value=100000))
def test_canonical_decimal(n):
    assert canonical(Money(amount=str(n)+'.00',currency='GBP'))==canonical(Money(amount=n,currency='GBP'))

def test_quote_time_and_publication():
    with pytest.raises(ValueError): Quote(instrument='X',bid='2',ask='1',source_time=T,received_at=T)
    with pytest.raises(ValueError): Quote(instrument='X',bid='1',ask='2',source_time=datetime(2024,1,1),received_at=T)
    f=Event(event_id='news',kind='feature',instrument='X',source_time=T,available_at='2024-01-01T00:10:00Z')
    with pytest.raises(ValueError): Snapshot(cutoff=T,features=(f,))
    with pytest.raises(ValueError): Bar(instrument='X',start=T,end='2024-01-01T00:01:00Z',available_at=T,basis='bid',open='1',high='2',low='1',close='1')


def test_hash_preserves_beyond_decimal_context_precision():
    a=Money(amount='1.1234567890123456789012345678901',currency='GBP')
    b=Money(amount='1.1234567890123456789012345678902',currency='GBP')
    assert digest(a)!=digest(b)
    assert str(a.amount) in canonical(a)

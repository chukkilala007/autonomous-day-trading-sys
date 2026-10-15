from decimal import Decimal as D
import pytest
from hypothesis import given,strategies as st
from trading_platform.risk.sizing import Contract,size
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import utc
T=utc('2024-01-01T00:00:00Z')

def inputs():
    e=Entry(instrument='X',side='buy',order_type='market',worst_fill='100',stop='99',target='103',expires_at='2024-01-01T01:00:00Z')
    c=Contract(instrument='X',account_currency='GBP',valuation_currency='GBP',quote_to_account='.8',contract_value_per_unit='1',commission_per_unit='.01',slippage_per_unit='.02',minimum='.1',maximum='1000',step='.3',tick='.01',margin_per_unit='1',verified_at=T,provenance='synthetic')
    return e,c

def test_conversion_rounding_and_costs():
    e,c=inputs();r=size(e,c,D('5'),now=T,free_margin=D('1000'),equity=D('1000'),reserve_fraction=D('.5'))
    assert r.unit_risk==D('.83') and r.risk<=5
    assert (r.quantity-c.minimum)%c.step==0
    with pytest.raises(ValueError): size(e,c,D('.01'),now=T,free_margin=D(1000),equity=D(1000),reserve_fraction=D('.5'))
    with pytest.raises(ValueError): Contract.model_validate_json(c.model_dump_json().replace('"linear":true','"linear":false'))
    data=c.model_dump();data.pop('commission_per_unit')
    with pytest.raises(ValueError): Contract(**data)

@given(st.integers(min_value=1,max_value=10000))
def test_never_round_above_budget(cents):
    e,c=inputs();budget=D(cents)/100
    if budget<D('.083'):
        with pytest.raises(ValueError): size(e,c,budget,now=T,free_margin=D(100000),equity=D(1000),reserve_fraction=D('.5'))
    else:
        r=size(e,c,budget,now=T,free_margin=D(100000),equity=D(1000),reserve_fraction=D('.5'))
        assert r.risk<=budget

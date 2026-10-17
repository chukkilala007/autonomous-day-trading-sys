import runpy
from datetime import timedelta
from decimal import Decimal as D
import pytest
from trading_platform.risk.sizing import Contract, ExactCosts, QuantityCost, size
from trading_platform.contracts.values import digest


def fixture():
    entry,contract=runpy.run_path('tests/risk/test_sizing.py')['inputs']()
    costs=ExactCosts(account_id='12',proposal_hash=digest(entry),evidence_hash='a'*64,observed_at=contract.verified_at,rows=(QuantityCost(quantity='.1',costs='2',margin='10'),QuantityCost(quantity='1',costs='2',margin='200'),QuantityCost(quantity='4',costs='3',margin='600')))
    data=contract.model_dump();data.update(commission_per_unit='0',slippage_per_unit='0',margin_per_unit='0',exact_costs=costs)
    return entry,Contract(**data)


def sized(entry,contract,budget='100',now=None):
    return size(entry,contract,D(budget),now=now or contract.verified_at,free_margin=D('1000'),equity=D('1000'),reserve_fraction=D('.5'))


def test_exact_quantities_minimum_fee_and_margin_tier():
    entry,contract=fixture()
    result=sized(entry,contract)
    assert result.quantity==1 and result.risk==D('2.8') and result.margin==200
    # A bigger risk budget cannot invent an unevidenced quantity or bypass margin.
    assert sized(entry,contract,'10000')==result
    assert sized(entry,contract,'2.5').quantity==D('.1')
    with pytest.raises(ValueError,match='no evidenced'):sized(entry,contract,'2')


def test_exact_economics_binding_freshness_and_schema():
    entry,contract=fixture()
    with pytest.raises(ValueError,match='proposal mismatch'):sized(entry.model_copy(update={'stop':D('98')}),contract)
    with pytest.raises(ValueError,match='stale quantity'):sized(entry,contract,now=contract.verified_at+timedelta(seconds=3))
    costs=contract.exact_costs
    for rows in ((costs.rows[0],costs.rows[0]),()):
        with pytest.raises(ValueError):ExactCosts(**(costs.model_dump()|{'rows':rows}))
    with pytest.raises(ValueError,match='ambiguous'):Contract(**(contract.model_dump()|{'commission_per_unit':'1'}))
    bad=costs.model_copy(update={'rows':(QuantityCost(quantity='.2',costs='1',margin='1'),)})
    with pytest.raises(ValueError,match='volume grid'):Contract(**(contract.model_dump()|{'exact_costs':bad}))

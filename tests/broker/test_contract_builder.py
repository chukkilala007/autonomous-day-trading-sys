import runpy
from datetime import timedelta
from decimal import Decimal as D
import pytest
from trading_platform.gateways.ctrader.contract_builder import Policy,build
from trading_platform.risk.sizing import size


def fixture():
    entry,old=runpy.run_path('tests/risk/test_sizing.py')['inputs']();now=old.verified_at
    policy=Policy(account_id='12',instrument='X',symbol_id=2,currency='GBP',tick='.01',minimum='1',maximum='100',step='1',contract_value_per_unit='1',roundtrip_cost_per_unit='.1',minimum_total_cost='3',fixed_cost='.5',cost_coverage='complete_roundtrip_upper_bound',classification='broker_verified',evidence_hash='a'*64,observed_at=now-timedelta(days=1),valid_until=now+timedelta(days=1))
    args=dict(account=12,now=now,quote_to_account='.8',conversion_observed_at=now,conversion_evidence_hash='b'*64,margin_request=dict(ctidTraderAccountId=12,symbolId=2,volume=[100,500,1000]),margin_response=dict(ctidTraderAccountId=12,moneyDigits=2,margin=[dict(volume=v,buyMargin=m,sellMargin=m+100) for v,m in [(100,1000),(500,40000),(1000,80000)]]),margin_observed_at=now)
    return policy,entry,args


def test_build_select_and_roundtrip_serialization():
    policy,entry,args=fixture();contract=build(policy,entry,**args)
    result=size(entry,contract,D('20'),now=args['now'],free_margin=D('1000'),equity=D('1000'),reserve_fraction=D('.5'))
    assert result.quantity==5 and result.risk==D('7.5') and result.margin==400
    from trading_platform.risk.sizing import Contract
    assert Contract.model_validate_json(contract.model_dump_json())==contract
    sell=entry.model_copy(update={'side':'sell','stop':D('101'),'target':D('97')})
    assert build(policy,sell,**args).exact_costs.rows[1].margin==401


@pytest.mark.parametrize('field,value', [('account',13),('quote_to_account','NaN'),('conversion_evidence_hash','missing')])
def test_missing_or_foreign_evidence_rejected(field,value):
    policy,entry,args=fixture()
    with pytest.raises(ValueError):build(policy,entry,**(args|{field:value}))


def test_stale_policy_margin_conversion_and_invalid_grid():
    policy,entry,args=fixture()
    for key in ('margin_observed_at','conversion_observed_at'):
        with pytest.raises(ValueError):build(policy,entry,**(args|{key:args['now']-timedelta(seconds=3)}))
    with pytest.raises(ValueError):build(policy.model_copy(update={'valid_until':args['now']}),entry,**args)
    with pytest.raises(ValueError):build(policy.model_copy(update={'step':D('3')}),entry,**args)
    with pytest.raises(ValueError):build(policy,entry,**(args|{'margin_response':args['margin_response']|{'margin':[]}}))

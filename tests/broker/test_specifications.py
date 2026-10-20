from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from trading_platform.gateways.ctrader.specifications import reconcile

T = datetime(2026, 10, 20, tzinfo=timezone.utc)


def probe():
    rows = []
    for sid, minimum, step, lot, digits in [(1, 100000, 100000, 10000000, 5), (41, 100, 100, 10000, 2)]:
        rows.append(dict(symbolId=str(sid), minVolume=str(minimum), maxVolume='5000000000',
                         stepVolume=str(step), lotSize=str(lot), digits=digits,
                         commissionType='USD_PER_MILLION_USD', preciseTradingCommissionRate='3500000000',
                         preciseMinCommission='0', minCommissionType='CURRENCY', minCommissionAsset='USD',
                         pnlConversionFeeRate=0))
    return dict(status='COLLECTED', mode='demo-readonly', orders_enabled=False, account_id='12',
                collected_at=T.isoformat(), symbols={'EURUSD': 1, 'XAUUSD': 41},
                metadata={'ctidTraderAccountId': '12', 'symbol': rows},
                economics={'trader': {'ctidTraderAccountId': '12', 'brokerName': 'FxPro'},
                           'account': {'currency': 'USD'}})


def test_public_comparison_preserves_conflict_without_promoting_capability():
    raw = probe(); before = deepcopy(raw)
    result = reconcile(raw, '12', T)
    assert raw == before
    assert result['symbols']['EURUSD']['conflicts'] == []
    gold = result['symbols']['XAUUSD']
    assert gold['conflicts'] == ['step']
    assert gold['comparisons']['step'] == {'public': '100', 'account': '1', 'matches': False}
    assert gold['published_tick'] == '0.01'
    assert result['symbols']['EURUSD']['published_tick'] is None
    assert not result['orders_enabled'] and not result['qualification_complete']
    assert 'capability' not in gold and gold['unresolved']


@pytest.mark.parametrize('fault', ['foreign', 'metadata', 'broker', 'stale', 'future', 'duplicate', 'write'])
def test_rejects_unbound_or_stale_specification_inputs(fault):
    raw = probe()
    if fault == 'foreign': raw['account_id'] = '13'
    if fault == 'metadata': raw['metadata']['ctidTraderAccountId'] = '13'
    if fault == 'broker': raw['economics']['trader']['brokerName'] = 'Other'
    if fault == 'stale': raw['collected_at'] = (T - timedelta(days=1)).isoformat()
    if fault == 'future': raw['collected_at'] = (T + timedelta(seconds=1)).isoformat()
    if fault == 'duplicate': raw['metadata']['symbol'].append(raw['metadata']['symbol'][0])
    if fault == 'write': raw['orders_enabled'] = True
    with pytest.raises(ValueError): reconcile(raw, '12', T)


def test_commission_change_is_a_conflict_and_not_silently_replaced():
    raw = probe()
    raw['metadata']['symbol'][0]['preciseTradingCommissionRate'] = '4000000000'
    result = reconcile(raw, '12', T)['symbols']['EURUSD']
    assert result['conflicts'] == ['commission_usd_per_million_per_side']
    assert Decimal(result['comparisons']['commission_usd_per_million_per_side']['account']) == 40

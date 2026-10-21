from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from trading_platform.gateways.ctrader import execution_review as module

T = datetime(2026, 10, 21, tzinfo=timezone.utc)


def probe():
    return {'status': 'COLLECTED', 'mode': 'demo-readonly', 'orders_enabled': False,
            'account_id': '12', 'collected_at': T.isoformat(), 'symbols': {'EURUSD': 1},
            'economics': {'trader': {'ctidTraderAccountId': '12', 'accountType': 'HEDGED',
                                    'accessRights': 'FULL_ACCESS', 'isLimitedRisk': False}},
            'metadata': {'ctidTraderAccountId': '12', 'symbol': [
                {'symbolId': '1', 'tradingMode': 'ENABLED', 'slDistance': 0, 'tpDistance': 0,
                 'distanceSetIn': 'SYMBOL_DISTANCE_IN_POINTS', 'digits': 5}]}}


def test_installed_sdk_profile_matches_transport_without_qualifying_broker():
    raw = probe(); before = deepcopy(raw)
    result = module.review(raw, '12', 'EURUSD', T)
    assert raw == before
    assert result['protocol']['sdk_mapping_matches_transport']
    assert result['protocol']['enums'] == {'LIMIT': 2, 'GOOD_TILL_DATE': 1, 'BUY': 1, 'SELL': 2}
    assert not result['profile_restrictions']
    assert not result['qualification_complete'] and not result['orders_enabled']
    assert not result['protocol']['broker_acceptance_observed']
    assert 'account_bound_tradable_tick' in result['remaining']
    assert 'attached_protection_trigger_and_acceptance' in result['remaining']
    assert 'capability' not in result


@pytest.mark.parametrize('fault', ['account', 'metadata', 'trader', 'stale', 'future', 'writes',
                                  'duplicate', 'missing_symbol', 'negative_distance'])
def test_invalid_inputs_rejected(fault):
    raw = probe()
    if fault == 'account': raw['account_id'] = '13'
    if fault == 'metadata': raw['metadata']['ctidTraderAccountId'] = '13'
    if fault == 'trader': raw['economics']['trader']['ctidTraderAccountId'] = '13'
    if fault == 'stale': raw['collected_at'] = (T - timedelta(days=1)).isoformat()
    if fault == 'future': raw['collected_at'] = (T + timedelta(seconds=1)).isoformat()
    if fault == 'writes': raw['orders_enabled'] = True
    if fault == 'duplicate': raw['metadata']['symbol'] *= 2
    if fault == 'missing_symbol': raw['metadata']['symbol'] = []
    if fault == 'negative_distance': raw['metadata']['symbol'][0]['slDistance'] = -1
    with pytest.raises(ValueError): module.review(raw, '12', 'EURUSD', T)


@pytest.mark.parametrize('field,value', [('isLimitedRisk', True), ('isLimitedRisk', 0),
                                       ('accountType', 'NETTED'), ('accessRights', 'CLOSE_ONLY')])
def test_incompatible_account_is_explicit_restriction(field, value):
    raw = probe(); raw['economics']['trader'][field] = value
    assert 'unsupported_account_' + field in module.review(raw, '12', 'EURUSD', T)['profile_restrictions']


def test_absence_is_not_a_default_and_zero_distance_does_not_qualify_protection():
    raw = probe(); del raw['economics']['trader']['isLimitedRisk']
    row = raw['metadata']['symbol'][0]; del row['slDistance']; del row['distanceSetIn']
    result = module.review(raw, '12', 'EURUSD', T)
    assert set(result['profile_restrictions']) == {'missing_account_isLimitedRisk', 'missing_slDistance', 'unknown_distance_unit'}
    assert result['symbol_observations']['slDistance'] is None
    assert result['symbol_observations']['tpDistance'] == 0
    assert not result['qualification_complete']


def test_disabled_symbol_and_sdk_mismatch_remain_blocking(monkeypatch):
    raw = probe(); raw['metadata']['symbol'][0]['tradingMode'] = 'CLOSE_ONLY'
    monkeypatch.setattr(module, 'protocol_profile', lambda: {'sdk_mapping_matches_transport': False})
    result = module.review(raw, '12', 'EURUSD', T)
    assert set(result['profile_restrictions']) == {'symbol_not_explicitly_enabled', 'sdk_profile_mismatch'}

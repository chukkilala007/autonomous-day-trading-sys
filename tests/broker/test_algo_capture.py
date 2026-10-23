from datetime import datetime, timezone, timedelta
import pytest
from trading_platform.gateways.ctrader.algo_capture import challenge, review

T = datetime(2026, 10, 21, tzinfo=timezone.utc)


def inputs():
    probe = dict(status='COLLECTED', mode='demo-readonly', orders_enabled=False, account_id='12',
                 collected_at=T.isoformat(), symbols={'EURUSD': 1},
                 economics={'account': {'currency': 'USD'}, 'trader': {'ctidTraderAccountId': '12',
                            'traderLogin': 900, 'brokerName': 'FxPro'}},
                 metadata={'ctidTraderAccountId': '12', 'symbol': [dict(symbolId=1, lotSize=10000000,
                           minVolume=100000, maxVolume=5000000000, stepVolume=100000, pipPosition=4)]})
    request = challenge(probe, '12', T)
    capture = dict(format=1, source='ctrader_algo_contract_exporter_v1', nonce=request['nonce'],
                   observed_at=T.isoformat(), is_live=False, running_mode='RealTime', broker_login='900',
                   broker='FxPro', currency='USD', symbol='EURUSD', tick_size='0.00001', pip_size='0.0001',
                   lot_size='100000', minimum='1000', maximum='50000000', step='1000')
    return probe, request, capture


def test_capture_binds_login_not_open_api_account_without_promoting():
    p, q, c = inputs(); r = review(c, q, p, '12', T)
    assert r['identity_checks_passed'] and r['tick_size'] == '0.00001'
    assert not r['orders_enabled'] and not r['qualification_complete']
    assert r['classification'] == 'operator_capture_pending_review'


@pytest.mark.parametrize('field,value', [('is_live', True), ('running_mode', 'SilentBacktesting'),
    ('broker_login', '12'), ('nonce', '0'*32), ('step', '1'), ('tick_size', 'NaN'),
    ('tick_size', '0'), ('tick_size', '0.00003'), ('pip_size', '0.01'), ('symbol', 'XAUUSD'),
    ('currency', 'EUR'), ('observed_at', '2026-10-21T00:00:01Z')])
def test_rejects_foreign_or_invalid_capture(field, value):
    p, q, c = inputs(); c[field] = value
    with pytest.raises(ValueError): review(c, q, p, '12', T)


def test_stale_capture_and_modified_probe_rejected():
    p, q, c = inputs()
    with pytest.raises(ValueError): review(c, q, p, '12', T + timedelta(minutes=6))
    p['metadata']['symbol'][0]['digits'] = 5
    with pytest.raises(ValueError): review(c, q, p, '12', T)


@pytest.mark.parametrize('fault', ['foreign', 'stale', 'missing_login', 'duplicate'])
def test_probe_identity_and_uniqueness(fault):
    p, q, c = inputs()
    if fault == 'foreign': p['account_id'] = '13'
    if fault == 'stale': p['collected_at'] = (T-timedelta(days=1)).isoformat()
    if fault == 'missing_login': del p['economics']['trader']['traderLogin']
    if fault == 'duplicate': p['metadata']['symbol'] *= 2
    with pytest.raises((ValueError, KeyError)):
        q = challenge(p, '12', T); c['nonce'] = q['nonce']; review(c, q, p, '12', T)


def nas_inputs():
    p,_,_=inputs()
    p['symbols']={'#USNDAQ100':1107}
    p['metadata']['symbol']=[dict(symbolId=1107,lotSize=100,minVolume=1,maxVolume=50000,stepVolume=1,pipPosition=0)]
    q=challenge(p,'12',T,'#USNDAQ100')
    c=dict(format=2,source='ctrader_algo_contract_exporter_v2',nonce=q['nonce'],observed_at=T.isoformat(),
        is_live=False,running_mode='RealTime',broker_login='900',broker='FxPro',currency='USD',
        symbol='#USNDAQ100',tick_size='.1',pip_size='1',lot_size='1',minimum='.01',maximum='500',step='.01',
        quote_currency='USD',tick_value='.2',pip_value='2')
    return p,q,c


def test_nas_capture_is_only_startup_value_observation():
    p,q,c=nas_inputs();r=review(c,q,p,'12',T)
    assert r['symbol']=='#USNDAQ100' and r['candidate_value_per_unit_per_price']=='2'
    assert r['monetary_value_classification']=='startup_snapshot_pending_review'
    assert not r['qualification_complete'] and not r['orders_enabled']


@pytest.mark.parametrize('field,value',[('symbol','EURUSD'),('quote_currency','EUR'),('tick_value','0'),
    ('pip_value','NaN'),('format',1),('source','ctrader_algo_contract_exporter_v1')])
def test_nas_capture_rejects_bad_identity_and_values(field,value):
    p,q,c=nas_inputs();c[field]=value
    with pytest.raises(ValueError):review(c,q,p,'12',T)


def test_new_capture_requires_symbol_bound_challenge():
    p,q,c=nas_inputs();q.pop('symbol')
    with pytest.raises(ValueError):review(c,q,p,'12',T)
    with pytest.raises(ValueError):challenge(p,'12',T,'XAUUSD')

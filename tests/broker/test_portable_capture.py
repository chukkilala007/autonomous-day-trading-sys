from datetime import timedelta
import pytest
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.algo_capture import challenge, review
from trading_platform.gateways.ctrader.broker_profile import AccountIdentity, CaptureScope
from test_algo_capture import inputs, T


def fixture():
    probe,_,raw=inputs()
    probe.update(generation=3,demo_binding=dict(account_id='12',generation=3,is_live=False))
    probe['economics'].update(account_id='12')
    probe['economics']['trader'].update(brokerName='Example Broker',accountType='HEDGED')
    probe['symbols']={'EUR/USD.c':1}
    scope=CaptureScope(identity=AccountIdentity(broker='Example Broker',account_id='12',environment='demo',currency='USD',account_type='HEDGED'),instrument='EURUSD',native_symbol='EUR/USD.c',symbol_id=1,quote_currency='USD',observed_at=T,valid_until=T+timedelta(hours=1))
    kw=dict(scope=scope,approved_scope_hash=digest(scope))
    req=challenge(probe,'12',T,'EUR/USD.c',**kw)
    raw.update(format=3,source='ctrader_algo_contract_exporter_v3',broker='Example Broker',symbol='EUR/USD.c',quote_currency='USD',tick_value='0.00001',pip_value='0.0001',scope_hash=digest(scope),nonce=req['nonce'])
    return probe,req,raw,kw


def test_portable_capture_keeps_observations_unqualified():
    p,q,r,k=fixture();out=review(r,q,p,'12',T,**k)
    assert out['instrument']=='EURUSD' and out['symbol']=='EUR/USD.c'
    assert out['scope_hash']==k['approved_scope_hash'] and not out['orders_enabled']
    assert out['classification']=='operator_capture_pending_review'


@pytest.mark.parametrize('fault',['broker','login','symbol','currency','quote','scope_hash','pin','live','generation','account','expired','request','legacy'])
def test_foreign_capture_or_scope_rejected(fault):
    p,q,r,k=fixture()
    if fault in ('broker','symbol','currency'):r[fault]='Other'
    if fault=='login':r['broker_login']='901'
    if fault=='quote':r['quote_currency']='GBP'
    if fault=='scope_hash':r['scope_hash']='b'*64
    if fault=='pin':k['approved_scope_hash']='b'*64
    if fault=='live':p['demo_binding']['is_live']=True
    if fault=='generation':p['generation']=4
    if fault=='account':p['economics']['account_id']='13'
    if fault=='expired':k['scope']=k['scope'].model_copy(update={'valid_until':T});k['approved_scope_hash']=digest(k['scope'])
    if fault=='request':q['broker']='Other'
    if fault=='legacy':r.update(format=2,source='ctrader_algo_contract_exporter_v2')
    with pytest.raises(ValueError):review(r,q,p,'12',T,**k)


def test_scope_required_and_challenge_cannot_switch_symbol():
    p,q,r,k=fixture()
    with pytest.raises(ValueError):review(r,q,p,'12',T)
    with pytest.raises(ValueError):challenge(p,'12',T,'OTHER',**k)
    with pytest.raises(ValueError):challenge(p,'12',T,'EUR/USD.c',approved_scope_hash=k['approved_scope_hash'])


def test_capture_labels_account_currency_without_assuming_quote_conversion():
    p,q,r,k=fixture()
    p['economics']['account']['currency']='GBP'
    scope=k['scope'].model_copy(update={'identity':k['scope'].identity.model_copy(update={'currency':'GBP'})})
    k=dict(scope=scope,approved_scope_hash=digest(scope))
    q=challenge(p,'12',T,'EUR/USD.c',**k)
    r.update(currency='GBP',scope_hash=digest(scope),nonce=q['nonce'])
    out=review(r,q,p,'12',T,**k)
    assert out['monetary_value_currency']=='GBP' and out['quote_currency']=='USD'
    assert not out['qualification_complete']

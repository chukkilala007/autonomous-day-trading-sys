from copy import deepcopy
from datetime import timedelta
import pytest
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.broker_profile import AccountIdentity, CaptureScope
from trading_platform.gateways.ctrader.evidence_providers.reviewed import DocumentGrid, ReviewedDocument, reconcile
from trading_platform.gateways.ctrader.evidence_providers.fxpro import reconcile as fxpro
from trading_platform.gateways.ctrader.specifications import reconcile as legacy
from test_specifications import probe, T


def fixture(broker='Example Broker'):
    p=probe()
    p.update(generation=1,demo_binding=dict(account_id='12',generation=1,is_live=False))
    p['economics'].update(account_id='12')
    p['economics']['trader'].update(brokerName=broker,accountType='HEDGED')
    p['symbols']={'EUR/USD.c':1}
    p['metadata']['symbol']=p['metadata']['symbol'][:1]
    identity=AccountIdentity(broker=broker,account_id='12',environment='demo',currency='USD',account_type='HEDGED')
    scope=CaptureScope(identity=identity,instrument='EURUSD',native_symbol='EUR/USD.c',symbol_id=1,
                       quote_currency='USD',observed_at=T,valid_until=T+timedelta(hours=1))
    doc=ReviewedDocument(scope=scope,source='synthetic document',source_hash='a'*64,
                         reviewed_at=T,valid_until=T+timedelta(hours=2),grid=DocumentGrid(minimum='1000',step='1000',lot='100000'))
    return p,doc


def run(p,d,**kw):
    args=dict(approved_document_hash=digest(d),now=T);args.update(kw)
    return reconcile(p,d,**args)


def test_legacy_output_unchanged():
    p=probe()
    assert legacy(p,'12',T)==fxpro(p,'12',T)
    assert legacy(p,'12',T)['symbols']['XAUUSD']['conflicts']==['step']


@pytest.mark.parametrize('broker',['FxPro','Example Broker'])
def test_generic_comparison_is_explicit_and_does_not_promote(broker):
    p,d=fixture(broker);before=deepcopy(p);out=run(p,d)
    assert p==before and out['conflicts']==[]
    assert out['identity']['broker']==broker and out['native_symbol']=='EUR/USD.c'
    assert out['classification']=='document_comparison_only'
    assert not out['orders_enabled'] and not out['qualification_complete']
    assert 'commission' not in out and 'published_tick' not in out
    assert out['valid_until']==d.scope.valid_until.isoformat()


def test_conflict_and_omitted_fields_preserved():
    p,d=fixture();d=d.model_copy(update={'grid':DocumentGrid(step='100')})
    out=run(p,d)
    assert out['conflicts']==['step'] and set(out['comparisons'])=={'step'}
    assert out['comparisons']['step']['account']=='1000'


@pytest.mark.parametrize('fault',['broker','account','environment','currency','type','generation','metadata','symbol','duplicate','alias','stale','future','pin','scope_expired','document_expired','negative'])
def test_foreign_or_stale_evidence_rejected(fault):
    p,d=fixture();kw={}
    if fault=='broker':p['economics']['trader']['brokerName']='Other'
    if fault=='account':p['economics']['account_id']='13'
    if fault=='environment':p['demo_binding']['is_live']=True
    if fault=='currency':p['economics']['account']['currency']='GBP'
    if fault=='type':p['economics']['trader']['accountType']='NETTED'
    if fault=='generation':p['generation']=2
    if fault=='metadata':p['metadata']['ctidTraderAccountId']='13'
    if fault=='symbol':p['symbols']['EUR/USD.c']=2
    if fault=='duplicate':p['metadata']['symbol']*=2
    if fault=='alias':p['symbols']['OTHER']=1
    if fault=='stale':p['collected_at']=(T-timedelta(days=1)).isoformat()
    if fault=='future':p['collected_at']=(T+timedelta(seconds=1)).isoformat()
    if fault=='pin':kw['approved_document_hash']='b'*64
    if fault=='scope_expired':kw['now']=T+timedelta(hours=1)
    if fault=='document_expired':d=d.model_copy(update={'valid_until':T})
    if fault=='negative':p['metadata']['symbol'][0]['minVolume']='-1'
    with pytest.raises(ValueError):run(p,d,**kw)


def test_document_from_other_broker_cannot_be_reused_or_relabelled():
    p,a=fixture('FxPro');_,b=fixture('Other')
    assert digest(a)!=digest(b)
    with pytest.raises(ValueError):run(p,b)
    with pytest.raises(ValueError):run(p,a,approved_document_hash=digest(b))
    p['economics']['trader']['brokerName']='Other'
    with pytest.raises(ValueError):fxpro(p,'12',T)


def test_empty_document_grid_rejected():
    with pytest.raises(ValueError):DocumentGrid()

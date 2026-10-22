from datetime import datetime, timezone, timedelta
import json
from decimal import Decimal
import pytest
from trading_platform.execution.attended_preview import Quote, Preconditions, prepare
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.valuation import Valuation

T=datetime(2026,10,22,tzinfo=timezone.utc)
H='a'*64


def inputs():
    e=Entry(instrument='EURUSD',side='buy',order_type='limit',entry='1.1',worst_fill='1.1',
            stop='1.099',target='1.102',expires_at=T+timedelta(seconds=60))
    q=Quote(account_id='12',instrument='EURUSD',observed_at=T,bid='1.1001',ask='1.1002',evidence_hash=H)
    v=Valuation.model_validate_json(json.dumps(dict(mode='demo',account_id='12',observed_at=T.isoformat(),
        classification='broker_verified',evidence_hash=H,currency='USD',balance='10000',equity='10000',
        free_margin='9000',history_complete=True,external_exposure=False,contracts={'EURUSD':dict(
        instrument='EURUSD',account_currency='USD',valuation_currency='USD',quote_to_account='1',
        contract_value_per_unit='1',commission_per_unit='0',slippage_per_unit='0',minimum='1000',
        maximum='50000000',step='1000',tick='0.00001',margin_per_unit='0',verified_at=T.isoformat(),
        provenance='synthetic-test',exact_costs=dict(account_id='12',proposal_hash=digest(e),evidence_hash=H,
        observed_at=T.isoformat(),rows=[dict(quantity='1000',costs='0.2',margin='40'),
                                       dict(quantity='2000',costs='0.4',margin='80')]))})))
    p=Preconditions(account_id='12',is_live=False,observed_at=T,valid_until=T+timedelta(minutes=1),
        proposal_hash=digest(e),source_hash=H,image_digest=H,policy_hash=H,reconciled_flat=True,
        unresolved_commands=0,writer_fenced=True,connected=True,
        **{k:H for k in ['account_profile_review','price_grid_review','protection_review','costs_review','entry_expiry_review']})
    return e,q,v,p


def test_fixed_quantity_costs_and_evidence_binding():
    e,q,v,p=inputs();r=prepare(e,q,v,p,T)
    assert str(r['quantity'])=='1000' and str(r['planned_loss'])=='1.200'
    assert r['margin']==40 and r['valid_until']==T+timedelta(seconds=2)
    assert r['status']=='PREPARED_NOT_AUTHORIZED' and r['orders_enabled'] is False
    assert r['submission_adapter_implemented'] is False
    assert r['preview_hash']==digest({k:v for k,v in r.items() if k!='preview_hash'})


@pytest.mark.parametrize('field', ['account_profile_review','price_grid_review','protection_review','costs_review','entry_expiry_review'])
def test_missing_reviews_explicitly_block(field):
    e,q,v,p=inputs();r=prepare(e,q,v,p.model_copy(update={field:None}),T)
    assert r['status']=='BLOCKED' and field.upper()+'_MISSING' in r['blockers']


@pytest.mark.parametrize('field,value,reason', [('connected',False,'DISCONNECTED'),
    ('writer_fenced',False,'WRITER_NOT_FENCED'),('reconciled_flat',False,'EXPOSURE_NOT_FLAT'),
    ('unresolved_commands',1,'UNRESOLVED_COMMANDS')])
def test_state_blocks(field,value,reason):
    e,q,v,p=inputs();assert reason in prepare(e,q,v,p.model_copy(update={field:value}),T)['blockers']


@pytest.mark.parametrize('fault',['foreign','future','stale','crossed','proposal','live','expiry','risk','margin','costs','grid','research'])
def test_rejects_unusable_inputs(fault):
    e,q,v,p=inputs()
    if fault=='foreign':q=q.model_copy(update={'account_id':'other'})
    if fault=='future':q=q.model_copy(update={'observed_at':T+timedelta(seconds=1)})
    if fault=='stale':q=q.model_copy(update={'observed_at':T-timedelta(seconds=3)})
    if fault=='crossed':q=q.model_copy(update={'bid':Decimal('1.2')})
    if fault=='proposal':p=p.model_copy(update={'proposal_hash':'b'*64})
    if fault=='live':p=p.model_copy(update={'is_live':True})
    if fault=='expiry':e=e.model_copy(update={'expires_at':T+timedelta(seconds=59)})
    if fault=='risk':v=v.model_copy(update={'equity':Decimal('100')})
    if fault=='margin':v=v.model_copy(update={'free_margin':Decimal('1000')})
    if fault=='costs':v.contracts['EURUSD']=v.contracts['EURUSD'].model_copy(update={'exact_costs':None})
    if fault=='grid':v.contracts['EURUSD']=v.contracts['EURUSD'].model_copy(update={'tick':Decimal('0.01')})
    if fault=='research':e=e.model_copy(update={'basis':'research'});p=p.model_copy(update={'proposal_hash':digest(e)})
    with pytest.raises(ValueError):prepare(e,q,v,p,T)


def test_boundary_age_has_no_remaining_preview_lifetime():
    e,q,v,p=inputs();q=q.model_copy(update={'observed_at':T-timedelta(seconds=2)})
    assert 'PREVIEW_ALREADY_EXPIRED' in prepare(e,q,v,p,T)['blockers']

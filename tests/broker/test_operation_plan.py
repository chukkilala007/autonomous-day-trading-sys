from datetime import timedelta
import pytest
from trading_platform.contracts.values import digest,utc
from trading_platform.gateways.ctrader.operation_plan import plan,REQUIRED
from trading_platform.gateways.ctrader.attended_binding import Binding,ReviewedBundle
from trading_platform.gateways.ctrader.launch_preflight import check
from test_portable_binding import configure
from test_attended_binding import rig,result,T


def resolve(x,bp):
    return plan(bp,x.entry,authenticated_identity=bp.identity,approved_hash=digest(bp),now=T)


@pytest.mark.parametrize('state,classification,reason',[('unsupported','broker_verified','BROKER_UNSUPPORTED'),
    ('unknown','broker_verified','EXPLICIT_UNKNOWN'),('supported','synthetic','UNQUALIFIED_EVIDENCE'),
    ('supported','protocol','UNQUALIFIED_EVIDENCE')])
def test_capability_diagnostics(rig,state,classification,reason):
    bundle,_=configure(rig);bp=bundle.broker_profile
    e=bp.evidence[0].model_copy(update=dict(state=state,classification=classification))
    bp=bp.model_copy(update={'evidence':(e,)+bp.evidence[1:]})
    r=resolve(rig,bp)
    assert r['status']=='BLOCKED' and r['requirements'][0]['reason']==reason
    assert r['blockers'][0].startswith('UNSUPPORTED:' if state=='unsupported' else 'UNKNOWN:')
    assert not r['orders_enabled'] and r['alternatives']==[]


@pytest.mark.parametrize('kind',['missing','expired','future'])
def test_missing_and_noncurrent_evidence(rig,kind):
    bundle,_=configure(rig);bp=bundle.broker_profile;e=bp.evidence[0]
    if kind=='missing':evidence=bp.evidence[1:]
    else:
        e=e.model_copy(update={'valid_until':T} if kind=='expired' else {'observed_at':T+timedelta(seconds=1)})
        evidence=(e,)+bp.evidence[1:]
    r=resolve(rig,bp.model_copy(update={'evidence':evidence}))
    assert r['blockers']==['UNKNOWN:'+REQUIRED[0]]


def test_supported_evidence_caps_lease(rig):
    bundle,_=configure(rig);bp=bundle.broker_profile
    bp=bp.model_copy(update={'evidence':(bp.evidence[0].model_copy(update={'valid_until':T+timedelta(seconds=1)}),)+bp.evidence[1:]})
    r=resolve(rig,bp)
    assert r['status']=='SUPPORTED_NOT_AUTHORIZED' and utc(r['valid_until'])==T+timedelta(seconds=1)


def test_preflight_and_runtime_block_absent_capabilities(rig):
    bundle,_=configure(rig);bp=bundle.broker_profile.model_copy(update={'evidence':()})
    bundle=ReviewedBundle(**dict(bundle.model_dump(),broker_profile=bp,broker_profile_hash=digest(bp)))
    out=check(bundle,rig.entry,account_id='12',approved_bundle_hash=digest(bundle),now=T)
    assert len(out['operation_plan']['blockers'])==3
    b=Binding(rig.session,rig.stream,rig.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=rig.epoch,now=lambda:T)
    with pytest.raises(ValueError,match='operation capability blocked'):result(b.preview(rig.entry))
    assert b._preview_lease is None


def test_no_sell_or_alternative_profile_substitution(rig):
    bundle,_=configure(rig);bp=bundle.broker_profile
    entry=rig.entry.model_copy(update={'side':'sell','stop':rig.entry.target,'target':rig.entry.stop})
    r=plan(bp,entry,authenticated_identity=bp.identity,approved_hash=digest(bp),now=T)
    assert 'UNSUPPORTED_OPERATION_PROFILE' in r['blockers'] and r['alternatives']==[]


def test_profile_pin_and_foreign_identity_rejected(rig):
    bundle,_=configure(rig);bp=bundle.broker_profile
    with pytest.raises(ValueError):plan(bp,rig.entry,authenticated_identity=bp.identity,approved_hash='b'*64,now=T)
    with pytest.raises(ValueError):plan(bp,rig.entry,authenticated_identity=bp.identity.model_copy(update={'broker':'Other'}),approved_hash=digest(bp),now=T)

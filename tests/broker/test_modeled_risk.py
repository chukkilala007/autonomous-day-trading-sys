from datetime import timedelta
from decimal import Decimal
import pytest
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.modeled_risk import DemoRiskPolicy
from trading_platform.gateways.ctrader.contract_builder import Policy
from trading_platform.gateways.ctrader.attended_binding import Binding,ReviewedBundle
from trading_platform.gateways.ctrader.attended_adapter import Approval,Adapter
from trading_platform.gateways.ctrader.first_test import Review,FirstTestTransport
from trading_platform.gateways.ctrader.execution_review import protocol_profile
from trading_platform.gateways.ctrader.orders import DemoTransport
from test_portable_binding import configure
from test_attended_adapter import adapter,rig,result,T,H


@pytest.fixture
def modeled(adapter):
    x,old,calls=adapter
    bundle,_=configure(x)
    common={k:v for k,v in bundle.policy.model_dump().items() if k not in
        ('roundtrip_cost_per_unit','minimum_total_cost','fixed_cost','cost_coverage','classification')}
    policy=DemoRiskPolicy(**common,classification='demo_modeled_risk',cost_coverage='reviewed_fees_plus_explicit_assumptions',
        fee_per_unit='.0002',minimum_fee='0',fixed_fee='0',adverse_exit_price_allowance='.0001',other_cost_allowance='0',
        fee_evidence_hash=H,assumptions_review_hash=H,realized_loss_bounded=False)
    bundle=ReviewedBundle(**dict(bundle.model_dump(),policy=policy))
    x.binding=Binding(x.session,x.stream,x.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=x.epoch,now=lambda:x.clock[0])
    x.raw['ProtoOASymbolByIdReq']['symbol'][0].update(scheduleTimeZone='UTC',schedule=[dict(startSecond=0,endSecond=604800)])
    review=Review(account_id='12',review_bundle_hash=x.binding.pin,protocol_hash=digest(protocol_profile()),observed_at=T,valid_until=T+timedelta(minutes=5),risk_semantics='demo_modeled_risk')
    approval=Approval(**dict(old.approval.model_dump(),review_bundle_hash=x.binding.pin,capability_hash=digest(review),risk_semantics='demo_modeled_risk',accepts_unbounded_realized_loss=True))
    gateway=FirstTestTransport(x.binding,review,approved_review_hash=digest(review),approved_approval_hash=digest(approval),authorized=True)
    a=Adapter(gateway,x.binding,old.ledger,review,approval,approved_hash=digest(approval),now=lambda:x.clock[0])
    return x,a,calls,policy,bundle


def test_modeled_preview_has_explicit_arithmetic_and_no_production_policy(modeled):
    x,a,calls,p,b=modeled
    r=result(x.binding.preview(x.entry))
    assert r['modeled_loss']==Decimal('1.3') and r['reviewed_fees']==Decimal('.2') and r['modeled_allowance']==Decimal('.1')
    assert r['realized_loss_bounded'] is False and r['risk_policy_hash']==digest(p)
    with pytest.raises(ValueError):Policy.model_validate_json(p.model_dump_json())
    with pytest.raises(ValueError,match='disabled'):result(a.submit(x.entry))
    assert calls==[]


def test_explicit_modeled_test_consumes_one_attempt(modeled):
    x,a,calls,_,_=modeled;a.enabled=True
    assert result(a.submit(x.entry))['status']=='AWAITING_RECONCILIATION'
    with pytest.raises(ValueError,match='consumed'):result(a.submit(x.entry))
    assert len(calls)==1


@pytest.mark.parametrize('change',[{'risk_semantics':'verified_bound'},{'accepts_unbounded_realized_loss':False}])
def test_approval_cannot_hide_modeled_risk(modeled,change):
    x,a,calls,_,_=modeled;approval=a.approval.model_copy(update=change)
    with pytest.raises(ValueError,match='modeled risk'):
        Adapter(a.gateway,x.binding,a.ledger,a.report,approval,approved_hash=digest(approval),now=lambda:T)
    assert calls==[]


def test_production_transport_rejects_modeled_adapter(modeled):
    x,a,calls,_,_=modeled
    with pytest.raises(ValueError,match='first-test'):
        Adapter(DemoTransport(x.db,x.session,authorized=True),x.binding,a.ledger,a.report,a.approval,approved_hash=digest(a.approval),now=lambda:T)


@pytest.mark.parametrize('change',[{'adverse_exit_price_allowance':'0'},{'other_cost_allowance':'-1'},
    {'realized_loss_bounded':True},{'assumptions_review_hash':None},{'currency':'GBP'}])
def test_invalid_model_rejected(modeled,change):
    *_,p,b=modeled
    with pytest.raises(ValueError):DemoRiskPolicy(**dict(p.model_dump(),**change))


def test_oversized_modeled_allowance_cannot_pass_budget(modeled):
    x,a,calls,p,b=modeled;p=p.model_copy(update={'adverse_exit_price_allowance':Decimal('.01')})
    b=ReviewedBundle(**dict(b.model_dump(),policy=p))
    x.binding=Binding(x.session,x.stream,x.db,b,approved_bundle_hash=digest(b),core_id='core',epoch=x.epoch,now=lambda:T)
    with pytest.raises(ValueError,match='budget'):result(x.binding.preview(x.entry))
    assert calls==[]

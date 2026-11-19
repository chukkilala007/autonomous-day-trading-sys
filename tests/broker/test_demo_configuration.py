from datetime import timedelta
import json
import pytest
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.demo_configuration import DemoConfiguration
from trading_platform.gateways.ctrader.attended_binding import Binding,ReviewedBundle
from trading_platform.gateways.ctrader.attended_adapter import Adapter,Approval
from trading_platform.gateways.ctrader.first_test import FirstTestTransport
from trading_platform.gateways.ctrader.operation_plan import plan,REQUIRED
from trading_platform.gateways.ctrader.settlement import DeferredCostPolicy,SettlementReviewRequired,settle
from test_modeled_risk import modeled,adapter,rig,result,T,H


def trial_bundle(modeled,broker='Example Broker'):
    x,a,calls,p,b=modeled
    identity=b.broker_profile.identity.model_copy(update={'broker':broker})
    bp=b.broker_profile.model_copy(update={'identity':identity,'evidence':()})
    cfg=DemoConfiguration(classification='operator_configured_demo_trial',identity=identity,
        instrument=p.instrument,symbol_id=p.symbol_id,operations=REQUIRED,
        assumptions={k:'Synthetic operator assumption, not broker verification' for k in
          ['price_grid','contract_value','fees','financing_adjustments','protection','expiry','recovery']},
        review_hash=H,observed_at=T,valid_until=T+timedelta(minutes=3))
    b=ReviewedBundle(**dict(b.model_dump(),broker_profile=bp,broker_profile_hash=digest(bp),demo_configuration=cfg))
    x.raw['ProtoOATraderReq']['trader']['brokerName']=broker
    return b,cfg


@pytest.mark.parametrize('broker',['FxPro','Independent cTrader Broker'])
def test_configured_unknowns_preview_without_promoting_capabilities(modeled,broker):
    x,a,calls,p,_=modeled;b,cfg=trial_bundle(modeled,broker)
    binding=Binding(x.session,x.stream,x.db,b,approved_bundle_hash=digest(b),core_id='core',epoch=x.epoch,now=lambda:T)
    preview=result(binding.preview(x.entry))
    assert preview['status']=='PREPARED_NOT_AUTHORIZED'
    assert preview['broker_assumptions']==cfg.assumptions
    assert preview['operation_plan']['status']=='DEMO_TRIAL_NOT_AUTHORIZED'
    assert all(r['state']=='unknown' for r in preview['operation_plan']['requirements'])
    assert b.broker_profile.capability(p.instrument,REQUIRED[0],authenticated_identity=cfg.identity,approved_hash=digest(b.broker_profile),now=T)=='unknown'
    assert not calls


@pytest.mark.parametrize('fault',['foreign','expired','live','missing_assumption','duplicate'])
def test_configuration_boundary(modeled,fault):
    x,a,calls,p,_=modeled;b,cfg=trial_bundle(modeled)
    data=cfg.model_dump()
    if fault=='foreign':data['identity']=cfg.identity.model_copy(update={'account_id':'13'})
    if fault=='expired':data['observed_at']=T-timedelta(minutes=2);data['valid_until']=T
    if fault=='live':data['identity']=cfg.identity.model_copy(update={'environment':'live'})
    if fault=='missing_assumption':data['assumptions'].pop('fees')
    if fault=='duplicate':data['operations']=(REQUIRED[0],REQUIRED[0])
    with pytest.raises(ValueError):
        changed=DemoConfiguration(**data)
        plan(b.broker_profile,x.entry,authenticated_identity=b.broker_profile.identity,approved_hash=digest(b.broker_profile),now=T,demo_configuration=changed)


def test_verified_policy_cannot_use_configured_trial(modeled):
    x,a,calls,p,_=modeled;b,cfg=trial_bundle(modeled)
    with pytest.raises(ValueError):ReviewedBundle(**dict(b.model_dump(),policy=x.bundle.policy))


def test_explicit_broker_unsupported_not_overridden(modeled):
    x,a,calls,p,original=modeled;b,cfg=trial_bundle(modeled)
    e=original.broker_profile.evidence[0].model_copy(update={'state':'unsupported','valid_until':T})
    bp=b.broker_profile.model_copy(update={'evidence':(e,)})
    r=plan(bp,x.entry,authenticated_identity=bp.identity,approved_hash=digest(bp),now=T,demo_configuration=cfg)
    assert r['blockers'] and r['status']=='BLOCKED'


def test_submission_requires_separate_explicit_ack_and_remains_single_attempt(modeled):
    x,a,calls,p,_=modeled;b,cfg=trial_bundle(modeled)
    binding=Binding(x.session,x.stream,x.db,b,approved_bundle_hash=digest(b),core_id='core',epoch=x.epoch,now=lambda:T)
    review=a.report.model_copy(update={'review_bundle_hash':digest(b)})
    values=dict(a.approval.model_dump(),review_bundle_hash=digest(b),capability_hash=digest(review))
    approval=Approval(**values)
    def compose(approval):
        g=FirstTestTransport(binding,review,approved_review_hash=digest(review),approved_approval_hash=digest(approval),authorized=True)
        return Adapter(g,binding,a.ledger,review,approval,approved_hash=digest(approval),now=lambda:T,enabled=True)
    with pytest.raises(ValueError,match='acknowledgement'):compose(approval)
    approved=Approval(**dict(values,accepts_unverified_broker_settings=True))
    active=compose(approved);assert result(active.submit(x.entry))['status']=='AWAITING_RECONCILIATION'
    with pytest.raises(ValueError,match='consumed'):result(active.submit(x.entry))
    assert len(calls)==1


def test_pending_costs_never_become_complete_settlement():
    p=DeferredCostPolicy(account_id='12',classification='settlement_review_pending',review_hash=H,verified_at=T,valid_until=T+timedelta(days=1))
    with pytest.raises(SettlementReviewRequired):settle('12',{},'1','2',1,[],T,T,T,p)
    with pytest.raises(ValueError,match='foreign'):settle('13',{},'1','2',1,[],T,T,T,p)


def test_monitor_reports_unreviewed_settlement_without_completion(adapter):
    from test_attended_monitor import setup
    x,a,calls,m,provider,bundle=setup(adapter,filled=True)
    def unreviewed(**kw):raise SettlementReviewRequired('not verified')
    provider.reconcile=unreviewed
    state=result(m.tick())
    assert state['status']=='SETTLEMENT_REVIEW_REQUIRED'
    assert not state.get('completed_once') and len(calls)==1


from test_attended_launcher import config


def test_launcher_loads_pinned_deferred_policy_only_with_trial(config,modeled):
    from trading_platform.gateways.ctrader.attended_launcher import inputs
    x,args,calls=config;b,cfg=trial_bundle(modeled)
    args.bundle.write_text(b.model_dump_json());args.approved_bundle_hash=digest(b)
    from trading_platform.gateways.ctrader.first_test import Review
    review=Review.model_validate_json(args.review.read_text()).model_copy(update={'review_bundle_hash':digest(b)})
    args.review.write_text(review.model_dump_json());args.approved_review_hash=digest(review)
    approval=Approval.model_validate_json(args.approval.read_text()).model_copy(update={'review_bundle_hash':digest(b),'capability_hash':digest(review),'accepts_unverified_broker_settings':True})
    args.approval.write_text(approval.model_dump_json());args.approved_approval_hash=digest(approval)
    costs=DeferredCostPolicy(account_id='12',classification='settlement_review_pending',review_hash=H,verified_at=T,valid_until=T+timedelta(days=1))
    args.cost_policy.write_text(costs.model_dump_json());args.approved_cost_policy_hash=digest(costs)
    assert isinstance(inputs(args,T).costs,DeferredCostPolicy)
    approval=approval.model_copy(update={'accepts_unverified_broker_settings':False})
    args.approval.write_text(approval.model_dump_json());args.approved_approval_hash=digest(approval)
    with pytest.raises(ValueError,match='acknowledgement'):inputs(args,T)

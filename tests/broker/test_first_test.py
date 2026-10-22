from datetime import timedelta
import json
import pytest
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.first_test import Review,FirstTestTransport
from trading_platform.gateways.ctrader.attended_adapter import Adapter,Approval
from trading_platform.gateways.ctrader.execution_review import protocol_profile
from trading_platform.gateways.ctrader.orders import DemoTransport
from test_attended_adapter import adapter,rig,result,T


@pytest.fixture
def first(adapter):
    x,old,calls=adapter
    x.raw['ProtoOASymbolByIdReq']['symbol'][0].update(scheduleTimeZone='UTC',schedule=[dict(startSecond=0,endSecond=604800)])
    review=Review(account_id='12',review_bundle_hash=x.binding.pin,protocol_hash=digest(protocol_profile()),observed_at=T,valid_until=T+timedelta(minutes=5))
    approval=old.approval.model_copy(update={'capability_hash':digest(review)})
    gateway=FirstTestTransport(x.binding,review,approved_review_hash=digest(review),approved_approval_hash=digest(approval),authorized=True)
    a=Adapter(gateway,x.binding,old.ledger,review,approval,approved_hash=digest(approval),now=lambda:x.clock[0],enabled=True)
    return x,a,calls


def test_first_test_without_fabricated_acceptance(first):
    x,a,calls=first
    assert a.report.acceptance_observed is False and not hasattr(a.report,'evidence')
    assert result(a.submit(x.entry))['status']=='AWAITING_RECONCILIATION'
    assert len(calls)==1 and calls[0].volume==100000
    with pytest.raises(ValueError):result(a.submit(x.entry))


@pytest.mark.parametrize('fault',['closed','unknown','expiry','protocol','bundle','disabled'])
def test_required_pretrade_facts_still_block(first,fault):
    x,a,calls=first
    raw=x.raw['ProtoOASymbolByIdReq']['symbol'][0]
    if fault=='closed':raw['schedule']=[dict(startSecond=0,endSecond=1)]
    if fault=='unknown':raw.pop('scheduleTimeZone')
    if fault=='expiry':x.clock[0]=T+timedelta(minutes=6)
    if fault=='protocol':
        # Even a pinned review cannot waive mismatching installed SDK encoding.
        r=a.report.model_copy(update={'protocol_hash':'f'*64})
        approval=a.approval.model_copy(update={'capability_hash':digest(r)})
        g=FirstTestTransport(x.binding,r,approved_review_hash=digest(r),approved_approval_hash=digest(approval),authorized=True)
        a=Adapter(g,x.binding,a.ledger,r,approval,approved_hash=digest(approval),now=lambda:x.clock[0],enabled=True)
    if fault=='bundle':x.binding.pin='b'*64
    if fault=='disabled':a.gateway.authorized=False
    with pytest.raises(ValueError):result(a.submit(x.entry))
    assert not calls


def test_direct_send_without_consumed_approval_rejected(first):
    x,a,calls=first
    with pytest.raises(ValueError,match='consumed'):
        a.gateway.send({},'core',1,a.report,None,T,T)
    assert not calls


def test_external_preview_cannot_replace_internal_lease(first):
    x,a,calls=first
    preview=result(x.binding.preview(x.entry))
    preview['planned_loss']='0';preview['blockers'].append('tampered')
    saved=json.loads(x.binding._preview_lease)['preview']
    assert saved['planned_loss']!='0' and not saved['blockers']


def test_production_transport_cannot_use_first_test_review(first):
    x,a,calls=first
    result(x.binding.preview(x.entry));q=x.binding._quote(T)
    from trading_platform.contracts.events import Quote
    quote=Quote(instrument='EURUSD',bid=q.bid,ask=q.ask,source_time=q.observed_at,received_at=T)
    command=dict(id='fake',instance='test',body=dict(decision=dict(environment='demo',proposal=json.loads(x.entry.model_dump_json())),size=dict(quantity='1000')))
    g=DemoTransport(x.db,x.session,authorized=True)
    with pytest.raises(AttributeError):g.prepare(command,'core',x.epoch,a.report,quote,T,T)
    assert not calls


def test_session_closes_before_cleanup_deadline(first):
    x,a,calls=first
    # Thursday UTC midnight is four days from Sunday; closure after60seconds.
    x.raw['ProtoOASymbolByIdReq']['symbol'][0]['schedule']=[dict(startSecond=0,endSecond=4*86400+60)]
    with pytest.raises(ValueError,match='session'):result(a.submit(x.entry))
    assert not calls

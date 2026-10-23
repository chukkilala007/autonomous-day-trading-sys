"""Synthetic contracts only; none of these values qualify NAS100 for execution."""
from datetime import timedelta
from decimal import Decimal
import json
import pytest
from trading_platform.contracts.orders import Entry
from trading_platform.contracts.events import Quote
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.attended_binding import Binding,ReviewedBundle
from trading_platform.gateways.ctrader.attended_adapter import Adapter,Approval
from trading_platform.gateways.ctrader.first_test import Review,FirstTestTransport
from trading_platform.gateways.ctrader.execution_review import protocol_profile
from trading_platform.gateways.ctrader.launch_preflight import check
from test_attended_adapter import adapter,rig,result,T,H


@pytest.fixture
def nas(adapter):
    x,old,calls=adapter
    policy=x.bundle.policy.model_copy(update=dict(instrument='#USNDAQ100',symbol_id=1107,
        tick=Decimal('.1'),minimum=Decimal('.01'),maximum=Decimal('500'),step=Decimal('.01'),
        contract_value_per_unit=Decimal('2')))
    bundle=ReviewedBundle(**dict(x.bundle.model_dump(),policy=policy,
        profile='USD_linear_absolute_protected_buy_limit_gtd',quantity='.01',contract_value_review=H))
    x.bundle=bundle
    x.stream.symbols={'#USNDAQ100':1107}
    x.feed.repaired('#USNDAQ100',T)
    x.feed.ingest_quote(Quote(instrument='#USNDAQ100',bid='29001',ask='29002',source_time=T,received_at=T))
    x.raw['ProtoOASymbolsListReq']['symbol']=[dict(symbolId='1107',symbolName='#USNDAQ100')]
    x.raw['ProtoOASymbolByIdReq']['symbol'][0].update(symbolId='1107',minVolume='1',stepVolume='1',maxVolume='50000',scheduleTimeZone='UTC',schedule=[dict(startSecond=0,endSecond=604800)])
    x.raw['ProtoOAExpectedMarginReq']['margin']=[dict(volume='1',buyMargin='1450',sellMargin='1450')]
    x.entry=Entry(instrument='#USNDAQ100',side='buy',order_type='limit',entry='29000',worst_fill='29000',stop='28990',target='29020',expires_at=T+timedelta(seconds=60))
    x.binding=Binding(x.session,x.stream,x.db,bundle,approved_bundle_hash=digest(bundle),core_id='core',epoch=x.epoch,now=lambda:x.clock[0])
    review=Review(account_id='12',symbol='#USNDAQ100',review_bundle_hash=x.binding.pin,protocol_hash=digest(protocol_profile()),observed_at=T,valid_until=T+timedelta(minutes=5))
    approval=Approval(account_id='12',test_id='nas-test',proposal_hash=digest(x.entry),review_bundle_hash=x.binding.pin,capability_hash=digest(review),approved_at=T,submit_before=T+timedelta(seconds=10),maximum_loss='5',quantity='.01')
    gateway=FirstTestTransport(x.binding,review,approved_review_hash=digest(review),approved_approval_hash=digest(approval),authorized=True)
    a=Adapter(gateway,x.binding,old.ledger,review,approval,approved_hash=digest(approval),now=lambda:x.clock[0],enabled=True)
    return x,a,calls


def test_fractional_preview_and_wire_volume(nas):
    x,a,calls=nas
    assert check(x.bundle,x.entry,account_id='12',approved_bundle_hash=x.binding.pin,now=T)['blockers']==[]
    preview=result(x.binding.preview(x.entry))
    assert preview['quantity']==Decimal('.01') and preview['margin']==Decimal('14.5')
    assert preview['planned_loss']==Decimal('.200002') # explicit multiplier2, not assumed1
    assert result(a.submit(x.entry))['status']=='AWAITING_RECONCILIATION'
    assert calls[0].symbolId==1107 and calls[0].volume==1
    assert x.calls[-1][1]['volume']==[1]
    with pytest.raises(ValueError,match='consumed'):result(a.submit(x.entry))


@pytest.mark.parametrize('change',[
    {'quantity':'1000'}, {'quantity':'.001'}, {'quantity':'0'},
    {'contract_value_review':None}, {'profile':'EURUSD_USD_absolute_protected_buy_limit_gtd'}])
def test_invalid_reviewed_profiles(nas,change):
    x,a,calls=nas
    with pytest.raises(ValueError):ReviewedBundle(**dict(x.bundle.model_dump(),**change))
    assert calls==[]


def test_missing_explicit_quantity_rejected(nas):
    x,_,_=nas;data=x.bundle.model_dump();data.pop('quantity')
    with pytest.raises(ValueError):ReviewedBundle(**data)


def test_approval_cannot_change_reviewed_quantity(nas):
    x,a,calls=nas;approval=a.approval.model_copy(update={'quantity':Decimal('.02')})
    with pytest.raises(ValueError,match='quantity'):
        Adapter(a.gateway,x.binding,a.ledger,a.report,approval,approved_hash=digest(approval),now=lambda:T)


def test_foreign_proposal_and_review_rejected(nas):
    x,a,calls=nas
    with pytest.raises(ValueError,match='symbol'):result(x.binding.preview(x.entry.model_copy(update={'instrument':'EURUSD'})))
    review=a.report.model_copy(update={'symbol':'EURUSD'})
    with pytest.raises(ValueError,match='symbol'):
        FirstTestTransport(x.binding,review,approved_review_hash=digest(review),approved_approval_hash=a.approved_hash)
    assert calls==[]


def test_fixed_loss_ceiling_still_applies(nas):
    x,a,calls=nas
    entry=x.entry.model_copy(update={'stop':Decimal('28000')})
    with pytest.raises(ValueError):result(x.binding.preview(entry))
    assert calls==[]


def test_fractional_owned_cleanup(nas):
    x,a,calls=nas;result(a.submit(x.entry))
    attempt=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(a.key,)).fetchone()['body'])
    send=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+attempt['command_id'],)).fetchone()['body'])
    f=send['fields'];trade=dict(symbolId='1107',tradeSide='BUY',volume='1')
    order=dict(orderId='7',clientOrderId=f['clientOrderId'],orderType='LIMIT',tradeData=trade,limitPrice=f['limitPrice'],stopLoss=f['stopLoss'],takeProfit=f['takeProfit'],orderStatus='ORDER_STATUS_FILLED',executedVolume='1',positionId='8',utcLastUpdateTimestamp='1')
    position=dict(positionId='8',tradeData=trade,positionStatus='POSITION_STATUS_OPEN',stopLoss=f['stopLoss'],takeProfit=f['takeProfit'],utcLastUpdateTimestamp='1',usedMargin='1450',moneyDigits=2)
    a.ledger.apply(dict(ctidTraderAccountId='12',order=order,position=position))
    x.raw['ProtoOAReconcileReq']['position']=[position]
    x.raw['ProtoOAGetPositionUnrealizedPnLReq']['positionUnrealizedPnL']=[dict(positionId='8',netUnrealizedPnL='0',grossUnrealizedPnL='0')]
    assert result(a.manage('close','8'))['status']=='CLEANUP_UNCONFIRMED'
    assert calls[-1].volume==1


def test_monitor_uses_fractional_exposure_ceiling(nas):
    from twisted.internet.defer import succeed
    from trading_platform.contracts.values import canonical
    from trading_platform.gateways.ctrader.provider import Provider
    from trading_platform.gateways.ctrader.attended_monitor import Monitor
    x,a,calls=nas;result(a.submit(x.entry))
    attempt=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(a.key,)).fetchone()['body'])
    key='gateway-send:'+attempt['command_id']
    send=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()['body'])
    send['broker_order_id']='7';x.feed.put(key,send)
    x.feed.put('broker-order:7',dict(owner=a.approval.test_id,terminal=False,remaining='.02',record={'executedVolume':'0'}))
    provider=Provider(x.session,x.db,lambda:{},lambda:None,lambda:T)
    provider.reconcile=lambda **kw:succeed(dict(account_id='12',history_complete=True,execution_events=[],valuation=canonical(dict(mode='demo',account_id='12',observed_at=T,classification='demo_observed',evidence_hash=H,currency='USD',balance='10000',equity='10000',free_margin='9000',history_complete=True,external_exposure=False,contracts={}))))
    m=Monitor(a,provider,now=lambda:T,enabled=True)
    assert result(m.tick())['status']=='EXPOSURE_BOUND_BREACH'
    assert len(calls)==1

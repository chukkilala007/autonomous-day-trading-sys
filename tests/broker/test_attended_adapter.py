import json
from datetime import timedelta
from decimal import Decimal
import pytest
from twisted.internet.defer import succeed
from trading_platform.contracts.values import digest,canonical
from trading_platform.gateways.ctrader.attended_adapter import Approval,Adapter
from trading_platform.gateways.ctrader.orders import DemoTransport,Fence
from trading_platform.gateways.ctrader.execution import ExecutionLedger
from trading_platform.gateways.ctrader.metadata import CapabilityReport,Evidence,REQUIRED
from test_attended_binding import rig,result,T,H


@pytest.fixture
def adapter(rig):
    x=rig;calls=[]
    x.client.send=lambda request,**kw:(calls.append(request) or succeed(object()))
    values={k:'synthetic-only' for k in REQUIRED}
    values.update(account_type='HEDGED',symbol_id='1',tick_grid='0.00001',volume_grid=json.dumps(dict(min='1000',max='50000000',step='1000')),session_state='OPEN',expiry='GOOD_TILL_DATE',order_types='["limit"]')
    report=CapabilityReport(account_id='12',symbol='EURUSD',evidence=tuple(Evidence(field=k,value=v,source='synthetic-test',classification='broker_verified',observed_at=T,valid_until=T+timedelta(minutes=5)) for k,v in values.items()))
    approval=Approval(account_id='12',test_id='test',proposal_hash=digest(x.entry),review_bundle_hash=x.binding.pin,capability_hash=digest(report),approved_at=T,submit_before=T+timedelta(seconds=10),maximum_loss='5')
    gateway=DemoTransport(x.db,x.session,authorized=True);ledger=ExecutionLedger(x.db,12)
    a=Adapter(gateway,x.binding,ledger,report,approval,approved_hash=digest(approval),now=lambda:x.clock[0])
    return x,a,calls


def test_disabled_then_single_consumed_submission(adapter):
    x,a,calls=adapter
    with pytest.raises(ValueError,match='disabled'):result(a.submit(x.entry))
    assert not calls
    a.enabled=True
    r=result(a.submit(x.entry));assert r['status']=='AWAITING_RECONCILIATION'
    assert len(calls)==1 and calls[0].volume==100000
    with pytest.raises(ValueError,match='consumed'):result(a.submit(x.entry))
    assert len(calls)==1


def test_timeout_does_not_allow_retry_or_new_test(adapter):
    x,a,calls=adapter;a.enabled=True
    def timeout(req,**kw):calls.append(req);raise TimeoutError('synthetic lost ack')
    x.client.send=timeout
    with pytest.raises(TimeoutError):result(a.submit(x.entry))
    with pytest.raises(ValueError):result(a.submit(x.entry))
    assert len(calls)==1
    assert x.db.connection.execute("SELECT 1 FROM checkpoints WHERE id LIKE 'gateway-send:%'").fetchone()


@pytest.mark.parametrize('fault',['expired','changed','loss','fence','capability'])
def test_submission_gates(adapter,fault):
    x,a,calls=adapter;a.enabled=True;entry=x.entry
    if fault=='expired':x.clock[0]+=timedelta(seconds=11)
    if fault=='changed':entry=entry.model_copy(update={'target':Decimal('1.103')})
    if fault=='loss':object.__setattr__(a.approval,'maximum_loss',Decimal('.5'))
    if fault=='fence':Fence(x.db,12).acquire('other')
    if fault=='capability':a.report=a.report.model_copy(update={'evidence':()})
    with pytest.raises(ValueError):result(a.submit(entry))
    assert not calls


def install_position(x,a):
    attempt=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(a.key,)).fetchone()['body'])
    send=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+attempt['command_id'],)).fetchone()['body'])
    f=send['fields'];trade=dict(symbolId='1',tradeSide='BUY',volume='100000')
    order=dict(orderId='7',clientOrderId=f['clientOrderId'],orderType='LIMIT',tradeData=trade,limitPrice=f['limitPrice'],stopLoss=f['stopLoss'],takeProfit=f['takeProfit'],orderStatus='ORDER_STATUS_FILLED',executedVolume='100000',positionId='8',utcLastUpdateTimestamp='1')
    position=dict(positionId='8',tradeData=trade,positionStatus='POSITION_STATUS_OPEN',stopLoss=f['stopLoss'],takeProfit=f['takeProfit'],utcLastUpdateTimestamp='1',usedMargin='4000',moneyDigits=2)
    # Exercise the same ledger projection used by the callback.
    a.ledger.apply(dict(ctidTraderAccountId='12',order=order,position=position))
    x.raw['ProtoOAReconcileReq']['position']=[position]
    x.raw['ProtoOAGetPositionUnrealizedPnLReq']['positionUnrealizedPnL']=[dict(positionId='8',netUnrealizedPnL='0')]
    return position


def test_owned_cleanup_once_not_flat_on_ack(adapter):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry));install_position(x,a)
    r=result(a.manage('close','8'));assert r['status']=='CLEANUP_UNCONFIRMED'
    assert calls[-1].DESCRIPTOR.name=='ProtoOAClosePositionReq' and calls[-1].volume==100000
    with pytest.raises(ValueError):result(a.manage('close','8'))
    assert len(calls)==2


@pytest.mark.parametrize('fault',['owner','revision','missing','oversize','action'])
def test_management_never_touches_foreign_or_stale_target(adapter,fault):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry));position=install_position(x,a)
    if fault=='owner':
        row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:8'").fetchone()['body']);row['owner']='other';x.feed.put('broker-position:8',row)
    if fault=='revision':position['utcLastUpdateTimestamp']='2'
    if fault=='missing':x.raw['ProtoOAReconcileReq']['position']=[];x.raw['ProtoOAGetPositionUnrealizedPnLReq']['positionUnrealizedPnL']=[]
    if fault=='oversize':
        row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:8'").fetchone()['body']);row['quantity']='2000';x.feed.put('broker-position:8',row)
    with pytest.raises(ValueError):result(a.manage('protect' if fault=='action' else 'close','8'))
    assert len(calls)==1


def test_cancel_original_pending_order_once(adapter):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry))
    attempt=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(a.key,)).fetchone()['body'])
    send=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+attempt['command_id'],)).fetchone()['body'])
    f=send['fields']
    order=dict(orderId='7',clientOrderId=f['clientOrderId'],orderType='LIMIT',tradeData=dict(symbolId='1',tradeSide='BUY',volume='100000'),limitPrice=f['limitPrice'],orderStatus='ORDER_STATUS_ACCEPTED',executedVolume='0',utcLastUpdateTimestamp='1')
    a.ledger.apply(dict(ctidTraderAccountId='12',order=order));x.raw['ProtoOAReconcileReq']['order']=[order]
    assert result(a.manage('cancel','7'))['status']=='CLEANUP_UNCONFIRMED'
    assert calls[-1].DESCRIPTOR.name=='ProtoOACancelOrderReq'
    with pytest.raises(ValueError):result(a.manage('cancel','7'))


def test_reconstruction_does_not_retry(adapter):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry))
    b=Adapter(a.gateway,x.binding,a.ledger,a.report,a.approval,approved_hash=digest(a.approval),now=lambda:x.clock[0],enabled=True)
    with pytest.raises(ValueError,match='consumed'):result(b.submit(x.entry))
    assert len(calls)==1


def test_same_owner_unrelated_position_rejected(adapter):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry));position=install_position(x,a)
    row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:8'").fetchone()['body'])
    row['record']=dict(position,positionId='9');x.feed.put('broker-position:9',row)
    x.raw['ProtoOAReconcileReq']['position']=[row['record']]
    x.raw['ProtoOAGetPositionUnrealizedPnLReq']['positionUnrealizedPnL']=[dict(positionId='9',netUnrealizedPnL='0')]
    with pytest.raises(ValueError,match='original'):result(a.manage('close','9'))
    assert len(calls)==1

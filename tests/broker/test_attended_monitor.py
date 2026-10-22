import json
from datetime import timedelta
from twisted.internet.defer import succeed, Deferred
from twisted.internet.task import Clock
import pytest
from trading_platform.contracts.values import canonical
from trading_platform.gateways.ctrader.attended_monitor import Monitor
from trading_platform.gateways.ctrader.provider import Provider
from test_attended_adapter import adapter,rig,result,install_position,T


def setup(adapter,filled=False):
    x,a,calls=adapter;a.enabled=True;result(a.submit(x.entry))
    if filled:install_position(x,a)
    else:
        attempt=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',(a.key,)).fetchone()['body'])
        send=json.loads(x.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+attempt['command_id'],)).fetchone()['body'])
        f=send['fields'];order=dict(orderId='7',clientOrderId=f['clientOrderId'],orderType='LIMIT',tradeData=dict(symbolId='1',tradeSide='BUY',volume='100000'),limitPrice=f['limitPrice'],orderStatus='ORDER_STATUS_ACCEPTED',executedVolume='0',utcLastUpdateTimestamp='1')
        a.ledger.apply(dict(ctidTraderAccountId='12',order=order));x.raw['ProtoOAReconcileReq']['order']=[order]
    provider=Provider(x.session,x.db,lambda:{},lambda:None,lambda:x.clock[0])
    def bundle():
        return dict(account_id='12',history_complete=True,execution_events=[],valuation=canonical(dict(mode='demo',account_id='12',observed_at=x.clock[0],classification='demo_observed',evidence_hash='a'*64,currency='USD',balance='10000',equity='10000',free_margin='9000',history_complete=True,external_exposure=False,contracts={})))
    provider.reconcile=lambda **kw:succeed(bundle())
    m=Monitor(a,provider,now=lambda:x.clock[0],enabled=True)
    return x,a,calls,m,provider,bundle


def test_cancel_at_twenty_once_across_restart(adapter):
    x,a,calls,m,p,b=setup(adapter)
    x.clock[0]=T+timedelta(seconds=19);assert result(m.tick())['status']=='MONITORING';assert len(calls)==1
    x.clock[0]+=timedelta(seconds=1);result(m.tick());assert calls[-1].DESCRIPTOR.name=='ProtoOACancelOrderReq'
    m=Monitor(a,p,now=lambda:x.clock[0],enabled=True)
    x.clock[0]=T+timedelta(seconds=61);assert result(m.tick())['status']=='EXPIRY_UNCONFIRMED'
    x.clock[0]=T+timedelta(seconds=121);assert result(m.tick())['status']=='CLEANUP_UNCONFIRMED'
    assert len(calls)==2


@pytest.mark.parametrize('protected', [False,True])
def test_close_unprotected_immediately_or_protected_by_deadline(adapter,protected):
    x,a,calls,m,p,b=setup(adapter,True)
    row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:8'").fetchone()['body'])
    row['protected']=protected;x.feed.put('broker-position:8',row)
    x.clock[0]=T+timedelta(seconds=1);result(m.tick())
    assert len(calls)==(1 if protected else 2)
    x.clock[0]=T+timedelta(seconds=120);assert result(m.tick())['status']=='CLEANUP_UNCONFIRMED'
    assert len(calls)==2 and calls[-1].DESCRIPTOR.name=='ProtoOAClosePositionReq'


def test_clock_regression_sticky_and_stop_not_complete(adapter):
    x,a,calls,m,p,b=setup(adapter);result(m.tick())
    x.clock[0]=T-timedelta(seconds=1);assert result(m.tick())['status']=='CLOCK_HALTED'
    x.clock[0]=T+timedelta(seconds=30);assert result(m.tick())['status']=='CLOCK_HALTED'
    m.stop()
    with pytest.raises(ValueError):result(m.tick())
    assert len(calls)==1


@pytest.mark.parametrize('fault',['foreign','incomplete','stale','disconnect','race'])
def test_bad_reconciliation_cannot_manage(adapter,fault):
    x,a,calls,m,p,b=setup(adapter);x.clock[0]=T+timedelta(seconds=20)
    value=b()
    if fault=='foreign':value['account_id']='13'
    if fault=='incomplete':value['history_complete']=False
    if fault=='stale':
        v=json.loads(value['valuation']);v['observed_at']=T.isoformat();value['valuation']=canonical(v)
    if fault=='disconnect':x.session.ready=False
    if fault=='race':
        def collect(**kw):a.binding.revision+=1;return succeed(value)
        p.reconcile=collect
    else:p.reconcile=lambda **kw:succeed(value)
    assert result(m.tick())['status']=='RECONCILIATION_REQUIRED' and len(calls)==1


def test_no_fill_terminal_is_not_fee_qualification(adapter):
    x,a,calls,m,p,b=setup(adapter)
    row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-order:7'").fetchone()['body'])
    row['terminal']=True;row['record']['orderStatus']='ORDER_STATUS_CANCELLED';x.feed.put('broker-order:7',row)
    assert result(m.tick())['status']=='TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'


def test_loop_does_not_submit_and_overlapping_tick_is_skipped(adapter):
    x,a,calls,m,p,b=setup(adapter);clock=Clock();pending=Deferred();p.reconcile=lambda **kw:pending
    m.start(clock);clock.advance(1)
    assert result(m.tick())['status']=='BUSY'
    pending.callback(b());m.stop();clock.advance(30)
    assert len(calls)==1


def test_completion_requires_settlement_and_late_exposure_revokes_it(adapter):
    x,a,calls,m,p,b=setup(adapter,True)
    row=json.loads(x.db.connection.execute("SELECT body FROM checkpoints WHERE id='broker-position:8'").fetchone()['body'])
    row['closed']=True;row['quantity']='0';x.feed.put('broker-position:8',row)
    assert result(m.tick())['status']=='AWAITING_SETTLEMENT'
    attempt=m._read(a.key)
    bundle=b();v=json.loads(bundle['valuation'])
    v['settlements']=[dict(command_id=attempt['command_id'],position_id='8',opened='1000',closed='1000',complete=True,costs_complete=True,history_from=T.isoformat(),opened_at=T.isoformat(),closed_at=T.isoformat(),history_to=T.isoformat(),movements=[dict(id='movement',position_id='8',currency='USD',amount='-1',evidence_hash='a'*64)],evidence_hash='b'*64)]
    bundle['valuation']=canonical(v);p.reconcile=lambda **kw:succeed(bundle)
    assert result(m.tick())['status']=='COMPLETE'
    row['closed']=False;row['quantity']='1000';x.feed.put('broker-position:8',row)
    # Real Provider rejects a reappeared settled position before publishing a
    # bundle; without a settlement bundle the monitor also revokes completion.
    p.reconcile=lambda **kw:succeed(b())
    assert result(m.tick())['status']=='POST_COMPLETION_EXPOSURE_HALT'


def test_cleanup_timeout_is_not_retried(adapter):
    x,a,calls,m,p,b=setup(adapter);x.clock[0]=T+timedelta(seconds=20)
    def timeout(req,**kw):calls.append(req);raise TimeoutError('synthetic')
    x.client.send=timeout
    assert result(m.tick())['status']=='RECONCILIATION_REQUIRED'
    result(m.tick());assert len(calls)==2


def test_stop_during_pending_read_prevents_later_cleanup_send(adapter):
    x,a,calls,m,p,b=setup(adapter);x.clock[0]=T+timedelta(seconds=20)
    pending=Deferred();p.reconcile=lambda **kw:pending
    d=m.tick();m.stop();pending.callback(b())
    assert result(d)['status']=='STOPPED_UNCONFIRMED' and len(calls)==1

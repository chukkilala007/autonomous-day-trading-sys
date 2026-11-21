"""Offline disconnect/authentication faults through the attended components."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from twisted.internet.defer import Deferred, succeed

from trading_platform.gateways.ctrader.attended_monitor import Monitor
from test_pending_lifecycle import pending_lifecycle
from test_attended_adapter import adapter, rig, result, install_position, T


def reconnect(x):
    # Exercise real connected/authenticate callbacks with synthetic credentials
    # and responses; no real token store, socket or broker is available.
    x.session.tokens = SimpleNamespace(read=lambda: dict(
        client_id='synthetic', client_secret='synthetic', access_token='synthetic',
        expires_at=x.session.now() + 3600))
    auth = []
    def wire(name, **fields):
        auth.append(name)
        if name == 'ProtoOAGetAccountListByAccessTokenReq':
            return succeed(dict(ctidTraderAccount=[dict(ctidTraderAccountId=12, isLive=False)]))
        return succeed(dict(ctidTraderAccountId=12))
    x.session.wire = wire
    x.session.connected()
    result(x.session.authenticated)
    assert x.session.ready and x.session.demo_binding['generation'] == x.session.generation
    assert auth == ['ProtoOAApplicationAuthReq', 'ProtoOAGetAccountListByAccessTokenReq',
                    'ProtoOAAccountAuthReq']


@pytest.mark.parametrize('filled', [False, True])
def test_active_exposure_reauth_reconciles_without_duplicate_entry(pending_lifecycle, filled):
    x, a, calls, m, p, baseline = pending_lifecycle
    if filled:
        position = install_position(x, a)
        order = dict(x.raw['ProtoOAReconcileReq']['order'][0])
        order.update(orderStatus='ORDER_STATUS_FILLED', executedVolume='100000',
                     utcLastUpdateTimestamp='3')
        x.raw['ProtoOAOrderListReq']['order'] = [order]
        x.raw['ProtoOAReconcileReq']['order'] = []
    assert result(m.tick())['status'] == 'MONITORING'
    generation = x.session.generation
    x.session.disconnected()
    x.clock[0] = T + timedelta(seconds=120 if filled else 20)
    assert result(m.tick())['status'] == 'RECONCILIATION_REQUIRED'
    assert len(calls) == 1
    reconnect(x)
    assert x.session.generation == generation + 2
    state = result(m.tick())
    assert state['status'] == ('CLEANUP_UNCONFIRMED' if filled else 'MONITORING')
    assert m.generation == x.session.generation
    expected = 'ProtoOAClosePositionReq' if filled else 'ProtoOACancelOrderReq'
    assert [c.DESCRIPTOR.name for c in calls] == ['ProtoOANewOrderReq', expected]
    # Monitor recreation and another reconnect cannot repeat a consumed cleanup.
    x.session.disconnected()
    reconnect(x)
    result(Monitor(a, p, now=lambda: x.clock[0], enabled=True).tick())
    assert len(calls) == 2
    with pytest.raises(ValueError):
        result(a.submit(x.entry))
    assert len(calls) == 2


def test_disconnect_during_history_discards_old_generation(pending_lifecycle):
    x, a, calls, m, p, baseline = pending_lifecycle
    x.clock[0] = T + timedelta(seconds=20)
    original = x.session.read
    pending = Deferred()
    x.session.read = lambda name, **kw: pending if name == 'ProtoOAOrderListReq' else original(name, **kw)
    tick = m.tick()
    assert not tick.called
    x.session.disconnected()
    reconnect(x)
    pending.callback(x.raw['ProtoOAOrderListReq'])
    assert result(tick)['status'] == 'RECONCILIATION_REQUIRED'
    assert m.generation is None and len(calls) == 1
    x.session.read = original
    assert result(m.tick())['status'] == 'MONITORING'
    assert len(calls) == 2


def test_lost_cancel_ack_stays_consumed_after_reauth(pending_lifecycle):
    x, a, calls, m, p, baseline = pending_lifecycle
    x.clock[0] = T + timedelta(seconds=20)
    def lost_ack(request, **kw):
        calls.append(request)
        x.session.disconnected()
        raise TimeoutError('synthetic acknowledgement loss')
    x.client.send = lost_ack
    assert result(m.tick())['status'] == 'RECONCILIATION_REQUIRED'
    assert len(calls) == 2
    reconnect(x)
    x.client.send = lambda *args, **kw: pytest.fail('must not resend after uncertain delivery')
    result(Monitor(a, p, now=lambda: x.clock[0], enabled=True).tick())
    assert len(calls) == 2
    assert not m._read(m.key).get('completed_once', False)

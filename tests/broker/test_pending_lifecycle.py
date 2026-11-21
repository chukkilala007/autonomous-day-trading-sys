"""Offline component integration; synthetic wire responses, no broker credentials."""
import copy
import json
from datetime import timedelta

import pytest

from trading_platform.gateways.ctrader.attended_monitor import Monitor
from trading_platform.gateways.ctrader.provider import Provider
from trading_platform.gateways.ctrader.unfilled import certify_unfilled
from test_attended_adapter import adapter, rig, result, install_position, T
from test_attended_monitor import setup


@pytest.fixture
def pending_lifecycle(adapter):
    x, a, calls = adapter
    baseline = result(a.economics.collect())
    x, a, calls, _, _, _ = setup(adapter)
    order = x.raw['ProtoOAReconcileReq']['order'][0]
    order['positionId'] = '8'
    order['utcLastUpdateTimestamp'] = '2'
    placeholder = dict(
        positionId='8', positionStatus='POSITION_STATUS_CREATED',
        tradeData=dict(symbolId='1', tradeSide='BUY', volume='0'),
        usedMargin='0', commission='0', swap='0', moneyDigits=2, price='0',
    )
    x.raw['ProtoOAReconcileReq']['position'] = [placeholder]
    x.raw['ProtoOAOrderListReq'] = dict(ctidTraderAccountId='12', hasMore=False, order=[])
    x.raw['ProtoOADealListReq'] = dict(ctidTraderAccountId='12', hasMore=False, deal=[])
    provider = Provider(x.session, x.db, lambda: {}, lambda: None, lambda: x.clock[0])
    monitor = Monitor(a, provider, now=lambda: x.clock[0], enabled=True)
    return x, a, calls, monitor, provider, baseline


def terminal(x, outcome):
    order = copy.deepcopy(x.raw['ProtoOAReconcileReq']['order'][0])
    order.update(orderStatus='ORDER_STATUS_' + outcome, utcLastUpdateTimestamp='3')
    x.raw['ProtoOAOrderListReq']['order'] = [order]
    x.raw['ProtoOAReconcileReq'].update(order=[], position=[])
    return order


@pytest.mark.parametrize('outcome', ['CANCELLED', 'EXPIRED'])
def test_placeholder_through_cleanup_and_review(pending_lifecycle, outcome):
    x, a, calls, m, p, baseline = pending_lifecycle
    x.clock[0] = T + timedelta(seconds=19)
    assert result(m.tick())['status'] == 'MONITORING'
    assert len(calls) == 1
    x.clock[0] = T + timedelta(seconds=20)
    assert result(m.tick())['status'] == 'MONITORING'
    assert [c.DESCRIPTOR.name for c in calls] == ['ProtoOANewOrderReq', 'ProtoOACancelOrderReq']
    # A cancel acknowledgement does not prove cancellation: expiry may win.
    order = terminal(x, outcome)
    assert result(m.tick())['status'] == 'TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'
    economics = result(p.economics.collect())
    evidence = dict(economics=economics, orders=[order], deals=[], cashflows=[],
                    history_from=baseline['observed_at'], history_to=x.clock[0].isoformat())
    certify_unfilled(x.db, '12', baseline, evidence, x.clock[0])
    assert result(m.tick())['status'] == 'COMPLETE'
    cleanup = json.loads(x.db.connection.execute(
        "SELECT body FROM checkpoints WHERE id LIKE 'gateway-management:%'").fetchone()[0])
    assert cleanup['status'] == 'TARGET_RESOLVED'
    assert cleanup['request_acceptance_confirmed'] is False
    assert result(Monitor(a, p, now=lambda: x.clock[0], enabled=True).tick())['status'] == 'COMPLETE'
    assert len(calls) == 2


def test_fill_wins_cancel_race_and_requires_owned_close(pending_lifecycle):
    x, a, calls, m, p, baseline = pending_lifecycle
    x.clock[0] = T + timedelta(seconds=20)
    result(m.tick())
    install_position(x, a)
    order = json.loads(x.db.connection.execute(
        "SELECT body FROM checkpoints WHERE id='broker-order:7'").fetchone()[0])['record']
    # A newer filled revision defeats the accepted pending snapshot.
    order.update(orderStatus='ORDER_STATUS_FILLED', executedVolume='100000',
                 utcLastUpdateTimestamp='3', positionId='8')
    x.raw['ProtoOAOrderListReq']['order'] = [order]
    x.raw['ProtoOAReconcileReq']['order'] = []
    assert result(m.tick())['status'] == 'MONITORING'
    assert len(calls) == 2
    x.clock[0] = T + timedelta(seconds=120)
    assert result(m.tick())['status'] == 'CLEANUP_UNCONFIRMED'
    assert calls[-1].DESCRIPTOR.name == 'ProtoOAClosePositionReq'
    assert calls[-1].positionId == 8 and calls[-1].volume == 100000
    result(m.tick())
    assert len(calls) == 3
    assert not x.db.connection.execute(
        "SELECT 1 FROM checkpoints WHERE id LIKE 'provider-unfilled:%'").fetchone()


def test_expiry_before_cancel_deadline_sends_no_cleanup(pending_lifecycle):
    x, a, calls, m, p, baseline = pending_lifecycle
    terminal(x, 'EXPIRED')
    x.clock[0] = T + timedelta(seconds=20)
    assert result(m.tick())['status'] == 'TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'
    assert len(calls) == 1


@pytest.mark.parametrize('field,value', [('commission', '1'), ('usedMargin', '1')])
def test_nonempty_placeholder_blocks_cleanup(pending_lifecycle, field, value):
    x, a, calls, m, p, baseline = pending_lifecycle
    x.raw['ProtoOAReconcileReq']['position'][0][field] = value
    x.clock[0] = T + timedelta(seconds=20)
    assert result(m.tick())['status'] == 'RECONCILIATION_REQUIRED'
    assert len(calls) == 1

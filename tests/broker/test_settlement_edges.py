"""Synthetic fee conventions and delayed partial-fill lifecycle acceptance."""
import copy
import json
from datetime import timedelta
from decimal import Decimal

import pytest

from trading_platform.gateways.ctrader.settlement import CostPolicy, settle
from test_pending_lifecycle import pending_lifecycle
from test_attended_adapter import adapter, rig, result, install_position, T


def policy(convention='positive_charge', source='close_detail'):
    return CostPolicy(account_id='12', evidence_hash='a'*64,
        verified_at=T-timedelta(days=1), valid_until=T+timedelta(days=1),
        commission_sign=convention, conversion_fee_sign=convention,
        closing_commission_source=source, closing_commission_excludes_opening=True,
        all_costs_covered=True)


def deals():
    base = dict(positionId='8', symbolId='1', dealStatus='PARTIALLY_FILLED',
                moneyDigits=2, tradeSide='BUY', orderId='7', executionPrice='1.1')
    rows = []
    for i, volume in enumerate(('15000', '25000')):
        rows.append(dict(base, dealId=str(i+1), filledVolume=volume, commission='25',
                         executionTimestamp=str(int((T+timedelta(seconds=i+1)).timestamp()*1000))))
    for i, volume in enumerate(('10000', '30000')):
        rows.append(dict(base, dealId=str(i+3), orderId='9', tradeSide='SELL',
            filledVolume=volume, commission='999',
            executionTimestamp=str(int((T+timedelta(seconds=121+i)).timestamp()*1000)),
            closePositionDetail=dict(closedVolume=volume, grossProfit='200',
                swap='-10', commission='50', pnlConversionFee='5', moneyDigits=2)))
    return rows


@pytest.mark.parametrize('convention', ['positive_charge', 'signed_cash'])
@pytest.mark.parametrize('source', ['deal', 'close_detail'])
def test_split_fills_count_each_cost_once(convention, source):
    rows = deals()
    if source == 'deal':
        for row in rows[2:]:
            row['commission'] = '50'
            row['closePositionDetail']['commission'] = '999'
    if convention == 'signed_cash':
        for row in rows:
            row['commission'] = str(-int(row['commission']))
            if 'closePositionDetail' in row:
                for key in ('commission', 'pnlConversionFee'):
                    row['closePositionDetail'][key] = str(-int(row['closePositionDetail'][key]))
    value = settle('12', dict(id='cmd', currency='USD'), '8', '7', Decimal('400'),
                   list(reversed(rows)), T, T+timedelta(seconds=123),
                   T+timedelta(seconds=123), policy(convention, source))
    assert value.opened == value.closed == 400
    assert len(value.movements) == 10
    assert sum(m.amount for m in value.movements) == Decimal('2.20')


def test_partial_remainder_cancel_waits_for_last_exit_deal(pending_lifecycle):
    x, a, calls, m, p, baseline = pending_lifecycle
    position = install_position(x, a)
    position['tradeData']['volume'] = '40000'
    position['utcLastUpdateTimestamp'] = '3'
    order = x.raw['ProtoOAReconcileReq']['order'][0]
    order.update(executedVolume='40000', utcLastUpdateTimestamp='3')
    x.clock[0] = T+timedelta(seconds=3)
    assert result(m.tick())['status'] == 'MONITORING'
    assert calls[-1].DESCRIPTOR.name == 'ProtoOACancelOrderReq'
    assert len(calls) == 2  # Partial fill cancels remainder before 20 seconds.
    order = copy.deepcopy(order)
    order.update(orderStatus='ORDER_STATUS_CANCELLED', utcLastUpdateTimestamp='4')
    x.raw['ProtoOAOrderListReq']['order'] = [order]
    x.raw['ProtoOAReconcileReq']['order'] = []
    x.clock[0] = T+timedelta(seconds=120)
    assert result(m.tick())['status'] == 'CLEANUP_UNCONFIRMED'
    assert calls[-1].volume == 40000
    p.cost_policy = policy
    x.clock[0] = T+timedelta(seconds=123)
    x.raw['ProtoOAReconcileReq']['position'] = []
    x.raw['ProtoOAGetPositionUnrealizedPnLReq']['positionUnrealizedPnL'] = []
    x.raw['ProtoOADealListReq']['deal'] = deals()[:-1]
    assert result(m.tick())['status'] == 'RECONCILIATION_REQUIRED'
    assert not x.db.connection.execute(
        "SELECT 1 FROM checkpoints WHERE id LIKE 'provider-settlement:%'").fetchone()
    x.raw['ProtoOADealListReq']['deal'] = list(reversed(deals()))
    assert result(m.tick())['status'] == 'COMPLETE'
    settlement = json.loads(x.db.connection.execute(
        "SELECT body FROM checkpoints WHERE id LIKE 'provider-settlement:%'").fetchone()[0])
    assert sum(Decimal(v['amount']) for v in settlement['movements']) == Decimal('2.20')
    cleanup = [json.loads(r[0]) for r in x.db.connection.execute(
        "SELECT body FROM checkpoints WHERE id LIKE 'gateway-management:%'")]
    assert all(v['status'] == 'TARGET_RESOLVED' for v in cleanup)
    result(m.tick())
    assert len(calls) == 3


@pytest.mark.parametrize('fault', ['account', 'owner', 'quantity', 'open', 'pending', 'missing', 'correlation'])
def test_filled_cancel_resolution_rejects_mismatched_evidence(pending_lifecycle, fault):
    from trading_platform.gateways.ctrader.management import settled_cancel_target
    test_partial_remainder_cancel_waits_for_last_exit_deal(pending_lifecycle)
    x, a, calls, m, p, baseline = pending_lifecycle
    assert settled_cancel_target(x.db.connection, '12', '7', a.approval.test_id)
    if fault == 'account':
        assert settled_cancel_target(x.db.connection, '13', '7', a.approval.test_id) is None
        return
    if fault == 'owner':
        assert settled_cancel_target(x.db.connection, '12', '7', 'foreign') is None
        return
    if fault == 'missing':
        x.db.connection.execute("DELETE FROM checkpoints WHERE id LIKE 'provider-settlement:%'")
    elif fault == 'open':
        position = m._read('broker-position:8')
        position.update(closed=False, quantity='1')
        x.feed.put('broker-position:8', position)
    else:
        order = m._read('broker-order:7')
        if fault == 'quantity':
            order['record']['executedVolume'] = '50000'
        if fault == 'pending':
            order['terminal'] = False
            order['record']['orderStatus'] = 'ORDER_STATUS_ACCEPTED'
        if fault == 'correlation':
            order['record']['clientOrderId'] = 'unrelated'
        x.feed.put('broker-order:7', order)
    assert settled_cancel_target(x.db.connection, '12', '7', a.approval.test_id) is None

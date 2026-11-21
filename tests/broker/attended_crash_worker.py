"""Subprocess-only synthetic attended recovery drill; never connects to a broker."""
import json
import os
from pathlib import Path
import signal
import sys
from datetime import timedelta

from twisted.internet.defer import succeed
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.attended_adapter import Approval
from trading_platform.gateways.ctrader.metadata import CapabilityReport
from trading_platform.gateways.ctrader.attended_monitor import Monitor
from trading_platform.gateways.ctrader.provider import Provider
from trading_platform.gateways.ctrader.unfilled import certify_unfilled
from test_attended_adapter import adapter, rig, result, install_position, T
from test_pending_lifecycle import pending_lifecycle, terminal


def run(root, phase, scenario):
    if phase == 'auto':
        phase = 'recover' if (root / 'broker.json').exists() else 'crash'
    fixture = rig.__wrapped__(root)
    x = next(fixture)
    components = adapter.__wrapped__(x)
    _, a, calls = components
    a.enabled = True
    def send(request, **kwargs):
        name = request.DESCRIPTOR.name
        with (root / 'wire.jsonl').open('a') as out:
            out.write(json.dumps(dict(name=name)) + '\n')
            out.flush()
            os.fsync(out.fileno())
        if phase == 'crash' and name == {
            'cancel': 'ProtoOACancelOrderReq', 'close': 'ProtoOAClosePositionReq'
        }.get(scenario):
            os.kill(os.getpid(), signal.SIGKILL)
        return succeed(object())
    x.client.send = send
    if phase == 'crash':
        x, a, calls, monitor, provider, baseline = pending_lifecycle.__wrapped__(components)
        if scenario == 'close':
            install_position(x, a)
            order = dict(x.raw['ProtoOAReconcileReq']['order'][0])
            order.update(orderStatus='ORDER_STATUS_FILLED', executedVolume='100000',
                         utcLastUpdateTimestamp='3')
            x.raw['ProtoOAOrderListReq']['order'] = [order]
            x.raw['ProtoOAReconcileReq']['order'] = []
        (root / 'broker.json').write_text(json.dumps(dict(raw=x.raw, baseline=baseline, approval=a.approval.model_dump_json(), report=a.report.model_dump_json())))
        assert result(monitor.tick())['status'] == 'MONITORING'
        if scenario == 'pending':
            os.kill(os.getpid(), signal.SIGKILL)
        x.clock[0] = T + timedelta(seconds=120 if scenario == 'close' else 20)
        result(monitor.tick())
        raise AssertionError('expected process kill was not reached')

    saved = json.loads((root / 'broker.json').read_text())
    x.raw.update(saved['raw'])
    a.approval = Approval.model_validate_json(saved['approval'])
    a.report = CapabilityReport.model_validate_json(saved['report'])
    a.approved_hash = digest(a.approval)
    x.clock[0] = T + timedelta(seconds=121 if scenario == 'close' else 21)
    provider = Provider(x.session, x.db, lambda: {}, lambda: None, lambda: x.clock[0])
    monitor = Monitor(a, provider, now=lambda: x.clock[0], enabled=True)
    attempt_before = monitor._read(a.key)
    assert attempt_before is not None
    assert x.db.connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    state = result(monitor.tick())
    assert state['status'] == ('CLEANUP_UNCONFIRMED' if scenario == 'close' else 'MONITORING'), state
    assert monitor._read(a.key) == attempt_before
    assert x.db.connection.execute(
        "SELECT count(*) FROM checkpoints WHERE id LIKE 'gateway-send:%'").fetchone()[0] == 1
    assert x.db.connection.execute(
        "SELECT count(*) FROM checkpoints WHERE id LIKE 'gateway-management:%'").fetchone()[0] == 1
    try:
        result(a.submit(x.entry))
    except ValueError:
        pass
    else:
        raise AssertionError('consumed entry was accepted')
    if scenario != 'close':
        order = terminal(x, 'CANCELLED')
        assert result(monitor.tick())['status'] == 'TERMINAL_UNFILLED_COST_REVIEW_REQUIRED'
        evidence = dict(economics=result(provider.economics.collect()), orders=[order],
                        deals=[], cashflows=[], history_from=saved['baseline']['observed_at'],
                        history_to=x.clock[0].isoformat())
        certify_unfilled(x.db, '12', saved['baseline'], evidence, x.clock[0])
        assert result(monitor.tick())['status'] == 'COMPLETE'
    else:
        # A missing close acknowledgement cannot establish flatness/settlement.
        assert not state.get('completed_once', False)
        assert monitor._read('broker-position:8')['quantity'] == '1000'
    result(monitor.tick())
    (root / 'recovery.json').write_text(json.dumps(dict(
        status=monitor._read(monitor.key)['status'], command_id=attempt_before['command_id'])))
    x.db.close()
    fixture.close()


if __name__ == '__main__':
    run(Path(sys.argv[1]), sys.argv[2], sys.argv[3])

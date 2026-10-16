import json,runpy
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
pytest.importorskip('ctrader_open_api')
from twisted.internet.defer import succeed,Deferred
from google.protobuf.json_format import ParseDict
from ctrader_open_api.messages.OpenApiMessages_pb2 import ProtoOAExecutionEvent
from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoMessage
from trading_platform.persistence.database import Database
from trading_platform.gateways.ctrader.execution import ExecutionLedger
from trading_platform.gateways.ctrader.lifecycle import Lifecycle

T=datetime(2026,10,16,tzinfo=timezone.utc)

def result(d):
    values=[];d.addCallback(values.append);assert values;return values[0]


def setup(db):
    calls=[]
    session=SimpleNamespace(account_id=12,ready=True,generation=1,refresh_if_due=lambda:succeed(None))
    stream=SimpleNamespace(repair=lambda:succeed(None),disconnected=lambda:calls.append('disconnect'),on_spot=lambda e:None)
    valuation=runpy.run_path('tests/broker/test_valuation.py')['fixture']()
    bundle=dict(account_id='12',history_complete=True,valuation=json.dumps(valuation),execution_events=[])
    provider=SimpleNamespace(reconcile=lambda **kwargs:(calls.append(kwargs) or succeed(bundle)))
    return Lifecycle(session,stream,ExecutionLedger(db,12),provider,lambda:T),bundle,calls


def test_cold_reconnect_and_stop_never_reuse_valuation(tmp_path):
    with Database(tmp_path/'db') as db:
        service,bundle,calls=setup(db)
        with pytest.raises(ValueError): service.valuation()
        assert result(service.poll()) and service.valuation()['account_id']=='12'
        assert calls[-1]=={'reconnect':True}
        assert result(service.poll()) and calls[-1]=={'reconnect':False}
        service.session.ready=False
        with pytest.raises(ValueError): service.valuation()
        assert not result(service.poll())
        service.session.ready=True;service.session.generation+=1
        assert result(service.poll()) and calls[-1]=={'reconnect':True}
        service.stop()
        assert not result(service.poll())
        with pytest.raises(ValueError): service.valuation()


@pytest.mark.parametrize('fault',['incomplete','foreign','generation','event','stopped','exception'])
def test_collection_races_cannot_publish_ready_observation(tmp_path,fault):
    with Database(tmp_path/'db') as db:
        service,bundle,calls=setup(db);pending=Deferred()
        service.provider.reconcile=lambda **_:pending
        running=service.poll()
        assert not result(service.poll())  # no overlapping provider requests
        if fault=='incomplete': bundle['history_complete']=False
        if fault=='foreign': bundle['execution_events']=[{'ctidTraderAccountId':'99'}]
        if fault=='generation': service.session.generation+=1
        if fault=='event': service.event_revision+=1
        if fault=='stopped': service.stop()
        if fault=='exception': pending.errback(ValueError('offline failure'))
        else: pending.callback(bundle)
        assert not result(running)
        with pytest.raises(ValueError): service.valuation()


def test_unsolicited_execution_invalidates_view_and_is_durable(tmp_path):
    with Database(tmp_path/'db') as db:
        service,bundle,calls=setup(db);assert result(service.poll())
        event=ParseDict({'ctidTraderAccountId':'12','executionType':'ORDER_ACCEPTED'},ProtoOAExecutionEvent())
        message=ProtoMessage(payloadType=event.payloadType,payload=event.SerializeToString())
        service.received(None,message)
        assert db.connection.execute("SELECT 1 FROM checkpoints WHERE id LIKE 'execution:%'").fetchone()
        with pytest.raises(ValueError): service.valuation()
        assert result(service.poll())
        service.received(None,object())
        with pytest.raises(ValueError): service.valuation()


def test_rpc_lifecycle_start_stop_drains_threads(tmp_path):
    # A separate reactor process allows a real thread/RPC shutdown without
    # polluting pytest's reactor or relying on a fake shutdown implementation.
    import subprocess,sys,textwrap
    code=textwrap.dedent('''
        from types import SimpleNamespace
        from twisted.internet import task,defer
        from trading_platform.gateways.ctrader.lifecycle import RunningGateway
        from trading_platform.gateways.ctrader.demo_server import Server
        @defer.inlineCallbacks
        def main(reactor):
            calls=[]
            client=SimpleNamespace(setMessageReceivedCallback=lambda cb:calls.append('callback'),
                startService=lambda:calls.append('start'),stopService=lambda:calls.append('stop'))
            lifecycle=SimpleNamespace(session=SimpleNamespace(client=client),received=lambda *a:None,
                poll=lambda:None,stopped=False,busy=False,stop=lambda:calls.append('invalidate'))
            server=Server(('127.0.0.1',0),'x'*40,lambda body:body)
            running=RunningGateway(lifecycle,server,reactor)
            running.start()
            yield running.stop()
            assert not running.thread.is_alive()
            assert calls==['callback','start','invalidate','stop'],calls
            yield running.stop()
            assert calls.count('stop')==1
        task.react(main)
    ''')
    completed=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=15)
    assert completed.returncode==0,completed.stderr


def test_stopping_inflight_poll_drains_without_publishing(tmp_path):
    with Database(tmp_path/'db') as db:
        service,bundle,calls=setup(db);pending=Deferred()
        service.provider.reconcile=lambda **_:pending
        running=service.poll();drained=[]
        service.drained.addCallback(lambda _:drained.append(True))
        service.stop()
        assert service.busy and not drained
        pending.callback(bundle)
        assert not result(running)
        assert drained==[True] and not service.busy
        with pytest.raises(ValueError): service.valuation()


def test_shutdown_timeout_does_not_hide_undrained_provider(tmp_path):
    from twisted.internet.task import Clock
    from twisted.internet.defer import TimeoutError
    from trading_platform.gateways.ctrader.lifecycle import RunningGateway
    with Database(tmp_path/'db') as db:
        service,bundle,calls=setup(db);pending=Deferred()
        service.provider.reconcile=lambda **_:pending
        service.session.client=SimpleNamespace(stopService=lambda:succeed(None))
        running_poll=service.poll();clock=Clock()
        server=SimpleNamespace(serve_forever=lambda:None,server_close=lambda:None)
        runner=RunningGateway(service,server,clock);failures=[]
        runner.stop().addErrback(failures.append)
        clock.advance(20)
        assert failures and failures[0].check(TimeoutError)
        assert service.busy and db.connection.execute('SELECT 1').fetchone()
        pending.callback(bundle)
        assert not result(running_poll)

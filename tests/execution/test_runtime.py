import json
from pathlib import Path
from trading_platform.persistence.database import Database
from trading_platform.simulation.broker import PaperBroker
from trading_platform.simulation.replay import load_registry
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.risk.sizing import Contract


def inputs():
    instances=[Instance.model_validate_json(Path(f'config/instances/{n}.json').read_text()) for n in ('tpr1','timer_fixture')]
    rows=json.loads(Path('tests/fixtures/paper.json').read_text())
    return instances,[(Event.model_validate_json(json.dumps(r['event'])),Snapshot.model_validate_json(json.dumps(r['snapshot'])),{k:Contract.model_validate_json(json.dumps(v)) for k,v in r['contracts'].items()}) for r in rows]


def test_complete_two_strategy_lifecycle_and_restart(tmp_path):
    instances,rows=inputs();state=tmp_path/'state.db';bp=tmp_path/'broker.json'
    with Database(state) as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(bp))
        runtime.process(*rows[0])
        status=runtime.status()
        assert len(status['orders'])==2, status
        assert len(status['active_risk'])==2,status
    # Both core and broker restart with independent persistent storage.
    with Database(state) as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(bp))
        for row in rows: runtime.process(*row)
        status=runtime.status()
        assert all(o['status']=='CLOSED' for o in status['orders']),status
        assert not status['positions'] and not status['active_risk'],status
        assert not status['rejections'],status
        assert len(runtime.broker.state['orders'])==2
        count=db.connection.execute('SELECT count(*) FROM decisions').fetchone()[0]
        for row in rows: runtime.process(*row)
        assert db.connection.execute('SELECT count(*) FROM decisions').fetchone()[0]==count
        assert len(runtime.broker.state['orders'])==2


def test_worker_failure_preserves_state_and_sibling_progress(tmp_path, monkeypatch):
    instances, rows = inputs()
    def failure(*args, **kwargs):
        raise TimeoutError('worker failed during evaluation')
    monkeypatch.setattr('trading_platform.runtime.paper.request', failure)
    with Database(tmp_path/'state.db') as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(),workers={'tpr1':('localhost',1,'unused')})
        before=db.connection.execute("SELECT state FROM instances WHERE id='tpr1'").fetchone()['state']
        runtime.process(*rows[0])
        state=runtime.status()
        failed=next(i for i in state['instances'] if i['id']=='tpr1')
        sibling=next(i for i in state['instances'] if i['id']=='timer_fixture')
        assert failed['cursor']==0 and failed['halt']
        assert sibling['cursor']==1 and not sibling['halt']
        assert db.connection.execute("SELECT state FROM instances WHERE id='tpr1'").fetchone()['state']==before
        assert len(state['orders'])==1 and state['orders'][0]['instance']=='timer_fixture'


def test_unknown_send_blocks_remaining_entries_until_reconciliation(tmp_path):
    instances,rows=inputs()
    class LostAck(PaperBroker):
        def submit(self,cmd,quote,now):
            return super().submit(cmd,quote,now,fault='timeout_after_accept')
    with Database(tmp_path/'state.db') as db:
        broker=LostAck()
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,broker)
        runtime.process(*rows[0])
        assert len(broker.state['orders'])==1
        assert any(o['status']=='UNKNOWN' for o in runtime.status()['orders'])
        assert len(runtime.status()['active_risk'])==1
        assert runtime.executor.reconcile(broker)
        assert len(broker.state['orders'])==1


def test_core_and_worker_killed_during_evaluation_replay_identically(tmp_path):
    """Kill actual processes mid-RPC, then replay the journal with healthy workers."""
    import multiprocessing as mp
    import socket
    from trading_platform.runtime.transport import receive
    context=mp.get_context('fork')
    ready=context.Event();evaluating=context.Event()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    port=listener.getsockname()[1]
    def worker():
        ready.set()
        conn,_=listener.accept()
        with conn:
            receive(conn);evaluating.set()
            context.Event().wait(20)
    def core():
        instances,rows=inputs()
        with Database(tmp_path/'crashed.db') as db:
            runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(tmp_path/'broker.json'),workers={'tpr1':('127.0.0.1',port,'test-token')})
            runtime.process(*rows[0])
    w=context.Process(target=worker);c=context.Process(target=core)
    try:
        w.start();assert ready.wait(5)
        c.start();assert evaluating.wait(5)
        c.kill();w.kill();c.join(5);w.join(5)
    finally:
        for proc in (c,w):
            if proc.is_alive(): proc.kill();proc.join(5)
        listener.close()
    instances,rows=inputs()
    results=[]
    for name in ('crashed','clean'):
        with Database(tmp_path/f'{name}.db') as db:
            runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker())
            for row in rows: runtime.process(*row)
            results.append(([tuple(r) for r in db.connection.execute('SELECT id,state,cursor FROM instances ORDER BY id')], [tuple(r) for r in db.connection.execute('SELECT id,body FROM decisions ORDER BY id')]))
            assert len(runtime.status()['orders'])==2
            assert not runtime.status()['positions'] and not runtime.status()['active_risk']
    assert results[0]==results[1]

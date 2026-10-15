import fcntl,json,runpy,time
import pytest
from trading_platform.persistence.database import Database
from trading_platform.persistence.archive import backup,restore,verify
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.simulation.broker import PaperBroker
from trading_platform.simulation.replay import load_registry


def test_quiesced_restore_retains_exposure_risk_and_halts(tmp_path):
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    original=tmp_path/'original.db';broker=tmp_path/'paper.json'
    with Database(original) as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(broker));runtime.process(*rows[0])
        ids={o['id'] for o in runtime.status()['orders']}
        with db.transaction() as c: c.execute('INSERT INTO halts VALUES (?,?)',('test','PERSISTENT_RISK_HALT'))
        with pytest.raises(ValueError): backup(original,broker,tmp_path/'active-backup')
    started=time.monotonic();manifest=backup(original,broker,tmp_path/'backup')
    assert manifest['rpo_events']==0 and verify(tmp_path/'backup')['event_cursor']==1
    restore(tmp_path/'backup',tmp_path/'restore')
    with Database(tmp_path/'restore'/'core.db') as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(tmp_path/'restore'/'paper.json'))
        assert {o['id'] for o in runtime.status()['orders']}==ids
        assert len(runtime.status()['active_risk'])==2
        assert runtime.controls.state()['paused']
        assert db.connection.execute('SELECT count(*) FROM halts').fetchone()[0]==2
        # Protection continues while entry halt remains latched.
        for row in rows[1:]: runtime.process(*row)
        assert not runtime.status()['positions'] and not runtime.status()['active_risk']
    assert time.monotonic()-started<10
    with pytest.raises(FileExistsError): restore(tmp_path/'backup',tmp_path/'restore')
    (tmp_path/'backup'/'broker.json').write_text('{}')
    with pytest.raises(ValueError,match='checksum'): verify(tmp_path/'backup')


def test_backup_rejects_active_simulator_lock(tmp_path):
    with Database(tmp_path/'db'): pass
    (tmp_path/'broker').write_text('{}')
    with open(str(tmp_path/'broker')+'.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError): backup(tmp_path/'db',tmp_path/'broker',tmp_path/'archive')

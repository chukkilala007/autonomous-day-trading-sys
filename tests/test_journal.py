import pytest
from trading_platform.persistence.database import Database
from trading_platform.runtime.journal import Journal
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.strategy import Evaluation
from trading_platform.contracts.decisions import Decision
T='2024-01-01T00:00:00Z'


def test_atomic_replay_cursor_and_evidence(tmp_path):
    p=tmp_path/'db'
    with Database(p) as db:
        j=Journal(db);j.register('a','p');j.register('b','p')
        e=Event(event_id='e',kind='timer',source_time=T,available_at=T,instrument='X')
        seq=j.append(e);assert j.append(e)==seq
        h=j.snapshot(Snapshot(cutoff=T))
        d=Decision(instance='a',account='p',environment='paper',package='p',config_hash='c',event_id='e',snapshot_hash=h,at=T,outcome='NO_ACTION')
        out=Evaluation(state='{"n":1}',decisions=(d,))
        with pytest.raises(RuntimeError): j.commit('a',seq,out,fail=True)
        assert db.connection.execute('SELECT count(*) FROM decisions').fetchone()[0]==0
        assert j.commit('a',seq,out)
        assert not j.commit('a',seq,out)
        with pytest.raises(ValueError): j.commit('b',seq+1,out)
        with pytest.raises(ValueError): j.append(e.model_copy(update={'payload':'{"changed":1}'}))
    with Database(p) as db:
        assert db.connection.execute("SELECT cursor FROM instances WHERE id='a'").fetchone()[0]==1
        assert db.connection.execute("SELECT cursor FROM instances WHERE id='b'").fetchone()[0]==0
        j=Journal(db);assert j.evidence(h)
        db.connection.execute('UPDATE snapshots SET body=? WHERE hash=?',('{"bad":true}',h))
        with pytest.raises(ValueError): j.evidence(h)

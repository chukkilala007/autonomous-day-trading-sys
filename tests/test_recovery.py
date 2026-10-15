import pytest
from trading_platform.persistence.database import Database
from trading_platform.runtime.journal import Journal
from trading_platform.runtime.recovery import Recovery


def test_latched_restart_and_owned_replacement(tmp_path):
    p=tmp_path/'db'
    with Database(p) as db:
        Journal(db).register('a','old');r=Recovery(db)
        r.halt('a','DATA_GAP');assert r.restart('a')['status']=='HALTED'
    with Database(p) as db:
        r=Recovery(db)
        with pytest.raises(ValueError): r.ready('a',coverage=True,reconciled=True)
        with pytest.raises(ValueError): r.ready('a',coverage=False,reconciled=True,explicit_resume=True)
        r.ready('a',coverage=True,reconciled=True,explicit_resume=True)
        db.connection.execute("INSERT INTO positions VALUES ('p','a','X','{}')")
        with pytest.raises(ValueError): r.replace('a','new')
        db.connection.execute('DELETE FROM positions')
        with pytest.raises(ValueError): r.replace('a','new')
        class Plugin:
            def migrate_state(self,old,state): return state
        r.replace('a','new',Plugin(),'1')
        assert r.status('a')['status']=='WARMING'

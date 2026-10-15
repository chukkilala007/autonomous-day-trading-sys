import sqlite3
import pytest
from trading_platform.persistence.database import Database


def test_writer_rollback_backup_restart(tmp_path):
    path=tmp_path/'state.db'
    with Database(path) as db:
        with pytest.raises(ValueError): Database(path)
        with pytest.raises(RuntimeError):
            with db.transaction() as c:
                c.execute("INSERT INTO halts VALUES ('x','test')")
                raise RuntimeError('crash')
        assert db.connection.execute('SELECT count(*) FROM halts').fetchone()[0]==0
        with db.transaction() as c: c.execute("INSERT INTO halts VALUES ('a','stop')")
        db.backup(tmp_path/'backup.db')
    with Database(path) as db:
        assert db.connection.execute('SELECT reason FROM halts').fetchone()[0]=='stop'
    with Database(tmp_path/'backup.db') as db:
        assert db.connection.execute('PRAGMA user_version').fetchone()[0]==1


def test_prior_schema_and_future_rejection(tmp_path):
    p=tmp_path/'old.db'
    with sqlite3.connect(p) as c: c.execute('PRAGMA user_version=0')
    with Database(p) as db: assert db.connection.execute('PRAGMA user_version').fetchone()[0]==1
    with sqlite3.connect(p) as c: c.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError): Database(p)

import subprocess,sys
from trading_platform.persistence.database import Database
from trading_platform.runtime.journal import Journal


def test_process_kill_rolls_back_and_releases_writer_lock(tmp_path):
    path=tmp_path/'state.db'
    with Database(path) as db: Journal(db).register('a','package')
    code="""
import os,sys
from trading_platform.persistence.database import Database
with Database(sys.argv[1]) as db:
    with db.transaction() as c:
        c.execute("UPDATE instances SET cursor=999,state='corrupt' WHERE id='a'")
        os._exit(9)
"""
    result=subprocess.run([sys.executable,'-c',code,str(path)])
    assert result.returncode==9
    with Database(path) as db:
        row=db.connection.execute("SELECT cursor,state FROM instances WHERE id='a'").fetchone()
        assert row['cursor']==0 and row['state']=='{}'

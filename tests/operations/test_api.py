import json,threading
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import pytest
from trading_platform.api.server import Server
from trading_platform.persistence.database import Database


def test_api_authentication_staleness_and_no_secret_checkpoint_leak(tmp_path):
    token='reader-test-token-'+32*'r'
    with Database(tmp_path/'db') as db:
        with db.transaction() as c:
            c.execute('INSERT INTO checkpoints VALUES (?,?)',('private:secret','{"secret":"must-not-leak"}'))
        server=Server(('127.0.0.1',0),db,token)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with pytest.raises(HTTPError) as err: urlopen(base+'/status')
            assert err.value.code==401
            with urlopen(Request(base+'/status',headers={'Authorization':'Bearer '+token})) as response:
                raw=response.read();body=json.loads(raw)
                assert body['stale'] and b'must-not-leak' not in raw
            with pytest.raises(HTTPError) as err: urlopen(Request(base+'/ready',headers={'Authorization':'Bearer '+token}))
            assert err.value.code==503
            with pytest.raises(HTTPError): urlopen(Request(base+'/evidence/../../secret',headers={'Authorization':'Bearer '+token}))
        finally: server.shutdown();server.server_close();thread.join(5)
    # UI/API lifetime never created a trading command or another writer.
    with Database(tmp_path/'db') as db: assert db.connection.execute('SELECT count(*) FROM commands').fetchone()[0]==0


def test_provider_status_is_explicitly_filtered_and_expiring(tmp_path):
    from datetime import datetime,timezone,timedelta
    from trading_platform.api.status import status
    from trading_platform.contracts.values import canonical
    at=datetime(2026,10,17,tzinfo=timezone.utc)
    with Database(tmp_path/'db') as db:
        value=dict(connection_state='CONNECTED',generation=3,coverage_complete=False,capability_blockers={'X':['tick_grid']},observed_at=at,source='actual_demo_readonly',access_token='must-not-leak')
        with db.transaction() as c:c.execute('INSERT INTO checkpoints VALUES (?,?)',('operations:provider',canonical(value)))
        data=status(db,at)['provider']
        assert data['generation']==3 and data['capability_blockers']=={'X':['tick_grid']} and not data['stale']
        assert 'access_token' not in data
        assert status(db,at+timedelta(seconds=31))['provider']['stale']

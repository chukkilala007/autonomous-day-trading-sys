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


def test_execution_dashboard_projects_pending_uncertain_settled_and_recovery(tmp_path):
    from datetime import datetime,timezone,timedelta
    from trading_platform.api.status import status
    from trading_platform.contracts.values import canonical
    from trading_platform.observability.alerts import Alerts
    at=datetime(2026,11,22,tzinfo=timezone.utc)
    with Database(tmp_path/'db') as db:
        with db.transaction() as c:
            for id,state,revision in (('pending','QUEUED',0),('uncertain','UNKNOWN',1),('settled','CLOSED',3)):
                c.execute('INSERT INTO commands(id,instance,instrument,body,status,revision) VALUES (?,?,?,?,?,?)',
                          (id,'strategy-a','EURUSD','{}',state,revision))
        alerts=Alerts(db)
        alerts.transition('broker',True,'BROKER_UNAVAILABLE',at.isoformat())
        alerts.transition('broker',False,'BROKER_UNAVAILABLE',(at+timedelta(seconds=1)).isoformat())
        view=status(db,at+timedelta(seconds=2))
        assert view['execution_summary']=={'PENDING':1,'UNCERTAIN':1,'SETTLED':1,'RECOVERED':1}
        assert {row['command_id']:row['state'] for row in view['execution_states']}=={
            'pending':'PENDING','uncertain':'UNCERTAIN','settled':'SETTLED'}
        assert [a['kind'] for a in view['alerts']]==['RECOVERED','OPEN']
        assert all('body' not in row for row in view['execution_states'])


def test_dashboard_assets_render_execution_and_alert_projection():
    from pathlib import Path
    root=Path('src/trading_platform/api')
    html=(root/'dashboard.html').read_text()
    script=(root/'dashboard.js').read_text()
    for id in ('execution-summary','execution-states','alerts'):
        assert f'id="{id}"' in html
        assert f"'{id}'" in script
    for state in ('PENDING','UNCERTAIN','SETTLED','RECOVERED'):
        assert state in script

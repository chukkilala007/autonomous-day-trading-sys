"""Local browser fixture with synthetic operations state; never connects to a broker."""
import signal
import tempfile
import threading
from datetime import datetime,timezone,timedelta

from trading_platform.api.dashboard import Handler as DashboardHandler,ThreadingHTTPServer
from trading_platform.api.server import Server
from trading_platform.contracts.values import canonical
from trading_platform.observability.alerts import Alerts
from trading_platform.persistence.database import Database


TOKEN='dashboard-fixture-reader-token-00000000000000000000'


def main():
    storage=tempfile.TemporaryDirectory()
    db=Database(storage.name+'/state.db')
    at=datetime.now(timezone.utc)
    with db.transaction() as c:
        c.execute('INSERT INTO checkpoints VALUES (?,?)',('operations:identity',canonical({'mode':'simulated','account_alias':'dashboard-acceptance'})))
        c.execute('INSERT INTO checkpoints VALUES (?,?)',('operations:provider',canonical({'connection_state':'CONNECTED','generation':4,'coverage_complete':True,'capability_blockers':{},'observed_at':at,'source':'synthetic_fixture'})))
        c.execute('INSERT INTO events(id,body) VALUES (?,?)',('latest',canonical({'available_at':at})))
        for id,state,revision in (('cmd-pending','QUEUED',0),('cmd-uncertain','UNKNOWN',1),('cmd-settled','CLOSED',3)):
            c.execute('INSERT INTO commands(id,instance,instrument,body,status,revision) VALUES (?,?,?,?,?,?)',(id,'strategy-a','EURUSD','{}',state,revision))
    alerts=Alerts(db)
    alerts.transition('broker',True,'BROKER_UNAVAILABLE',(at-timedelta(seconds=1)).isoformat())
    alerts.transition('broker',False,'BROKER_UNAVAILABLE',at.isoformat())
    api=Server(('0.0.0.0',19010),db,TOKEN)
    dashboard=ThreadingHTTPServer(('0.0.0.0',18080),DashboardHandler)
    dashboard.upstream='http://127.0.0.1:19010'
    threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (api,dashboard)]
    for thread in threads: thread.start()
    stopped=threading.Event()
    signal.signal(signal.SIGTERM,lambda *_:stopped.set())
    signal.signal(signal.SIGINT,lambda *_:stopped.set())
    try: stopped.wait()
    finally:
        for server in (dashboard,api): server.shutdown();server.server_close()
        for thread in threads: thread.join(5)
        db.close();storage.cleanup()


if __name__=='__main__': main()

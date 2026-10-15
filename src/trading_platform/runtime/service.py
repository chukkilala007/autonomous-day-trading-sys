"""Container paper service consuming a versioned synthetic/recorded input file."""
import json,signal,time
from pathlib import Path
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.risk.sizing import Contract
from trading_platform.persistence.database import Database
from trading_platform.simulation.replay import load_registry,records
from trading_platform.simulation.server import RemoteBroker
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.api.server import serving
from trading_platform.contracts.values import canonical


def run(args):
    settings=json.loads(Path(args.deployment).read_text())
    token=lambda name:Path(settings['tokens'][name]).read_text().strip()
    instances=[Instance.model_validate_json(Path(p).read_text()) for p in settings['instances']]
    workers={k:(v['host'],v.get('port',9000),token(k)) for k,v in settings['workers'].items()}
    broker=RemoteBroker(settings['broker']['host'],settings['broker'].get('port',9000),token('broker'))
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    with Database(args.state) as db, serving(db,settings.get("api")):
        with db.transaction() as c:
            c.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?)",("operations:identity",canonical({"mode":"paper","account_alias":instances[0].account.alias,"config_hashes":{i.instance_id:i.hash for i in instances}})))
        runtime=PaperRuntime(db,load_registry(settings['registry']),instances,broker,workers,settings.get('factors'))
        while not stopping:
            normalized=records(args.input)
            raw=json.loads(Path(args.input).read_text())
            by_event={r['event']['event_id']:r for r in raw}
            for event,snapshot in normalized:
                if stopping: break
                key='driver:'+event.event_id
                if db.connection.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): continue
                contracts={k:Contract.model_validate_json(json.dumps(v)) for k,v in by_event[event.event_id]['contracts'].items()}
                status=runtime.process(event,snapshot,contracts)
                with db.transaction() as c: c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(key,json.dumps({'complete':True})))
                print(json.dumps({'event':event.event_id,'status':status}),flush=True)
                until=time.monotonic()+args.step_delay
                while time.monotonic()<until and not stopping: time.sleep(.1)
            if args.once:
                status=runtime.status();print(json.dumps(status),flush=True)
                return 1 if any(i['halt'] for i in status['instances']) else 0
            runtime.executor.reconcile(broker)
            time.sleep(.5)
        # Persistence and broker-held paper protections survive process shutdown.
        print(json.dumps({'stopped':True,'status':runtime.status()}),flush=True)
    return 0

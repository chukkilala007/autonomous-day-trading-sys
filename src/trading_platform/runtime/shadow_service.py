"""Separate core consuming gateway snapshots and isolated strategy workers."""
import argparse,json,signal,time
from datetime import datetime,timezone
from pathlib import Path
from trading_platform.contracts.config import Instance
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.events import Event
from trading_platform.contracts.values import canonical,digest
from trading_platform.persistence.database import Database
from trading_platform.simulation.replay import load_registry
from trading_platform.runtime.transport import request
from trading_platform.runtime.shadow import ShadowRuntime
from trading_platform.api.server import serving


def main():
    p=argparse.ArgumentParser();p.add_argument('--deployment',required=True);p.add_argument('--state',required=True);args=p.parse_args()
    config=json.loads(Path(args.deployment).read_text());token=lambda key:Path(config['tokens'][key]).read_text().strip()
    instances=[Instance.model_validate_json(Path(path).read_text()) for path in config['instances']]
    workers={k:(v['host'],v.get('port',9000),token(k)) for k,v in config['workers'].items()}
    if set(workers)!={i.instance_id for i in instances}: raise ValueError('every shadow instance requires an isolated worker')
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    with Database(args.state) as db,serving(db,config.get('api')):
        runtime=ShadowRuntime(db,load_registry(config['registry']),instances,workers)
        with db.transaction() as c: c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:identity',canonical({'mode':'shadow','account_alias':instances[0].account.alias,'config_hashes':{i.instance_id:i.hash for i in instances}})))
        while not stopped:
            received=False
            try:
                data=request(config['gateway']['host'],config['gateway'].get('port',9100),token('gateway'),'shadow-core',{'op':'snapshot'})
                received=True
                with db.transaction() as c:c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:provider',canonical(data.get('provider',{}))))
                snapshot=Snapshot.model_validate_json(json.dumps(data['snapshot']))
                wall=datetime.now(timezone.utc)
                if not 0<=(wall-snapshot.cutoff).total_seconds()<=2: raise ValueError('stale gateway snapshot')
                if not snapshot.coverage_complete: raise ValueError('incomplete market coverage')
                event=Event(event_id='shadow:'+snapshot.hash,kind='timer',instrument='ACCOUNT',source_time=snapshot.cutoff,available_at=snapshot.cutoff)
                runtime.process(event,snapshot,data['account'])
                with db.transaction() as c: c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('shadow:account',canonical(data['account'])))
                print(json.dumps({'mode':'shadow','processed':event.event_id,'order_writes':0}),flush=True)
            except (ValueError,OSError,TimeoutError):
                if not received:
                    with db.transaction() as c:c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:provider',canonical(dict(connection_state='UNAVAILABLE',coverage_complete=False,observed_at=datetime.now(timezone.utc),source='gateway_rpc'))))
                print('{"mode":"shadow","ready":false,"reason":"COVERAGE_OR_RECONCILIATION_REQUIRED"}',flush=True)
            time.sleep(1)

if __name__=='__main__': main()

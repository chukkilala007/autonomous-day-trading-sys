"""Demo core service, without credentials or simulated tick execution.

An authorized provider gateway and fresh audited valuation input are required.
Default deployment files do not start this service or enable broker orders.
"""
import argparse,json,signal,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.values import canonical
from trading_platform.execution.demo_broker import DemoBroker
from trading_platform.persistence.database import Database
from trading_platform.risk.sizing import Contract
from trading_platform.runtime.demo import DemoRuntime
from trading_platform.simulation.replay import load_registry
from trading_platform.api.server import serving
from trading_platform.observability.alerts import Alerts


def cycle(runtime):
    data=runtime.broker.call('snapshot')
    snapshot=Snapshot.model_validate_json(json.dumps(data['snapshot']))
    now=runtime.broker.now()
    if not snapshot.coverage_complete or not 0<=(now-snapshot.cutoff).total_seconds()<=2: raise ValueError('fresh coverage required')
    contracts={k:Contract.model_validate_json(json.dumps(v)) for k,v in data['contracts'].items()}
    event=Event(event_id='demo:'+snapshot.hash,kind='timer',instrument='ACCOUNT',source_time=snapshot.cutoff,available_at=snapshot.cutoff)
    runtime.process(event,snapshot,contracts)
    runtime.broker.call('recover')
    runtime.executor.reconcile(runtime.broker)
    runtime.controls.pump(runtime,now,snapshot)
    return runtime.status()


def main():
    p=argparse.ArgumentParser();p.add_argument('--deployment',required=True);p.add_argument('--state',required=True);args=p.parse_args()
    config=json.loads(Path(args.deployment).read_text())
    if config.get('mode')!='demo': raise ValueError('explicit demo deployment required')
    token=lambda name:Path(config['tokens'][name]).read_text().strip()
    instances=[Instance.model_validate_json(Path(path).read_text()) for path in config['instances']]
    workers={name:(value['host'],value.get('port',9000),token(name)) for name,value in config['workers'].items()}
    if set(workers)!={i.instance_id for i in instances}: raise ValueError('isolated worker required for every instance')
    stopped=False
    def stop(*_):
        nonlocal stopped
        stopped=True
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    # Lock core state before obtaining a gateway fence, so a duplicate process cannot fence a healthy writer.
    with Database(args.state) as db,serving(db,config.get('api')):
        broker=DemoBroker(config['broker']['host'],config['broker'].get('port',9200),token('broker'),config['account_id'],str(uuid.uuid4()))
        runtime=DemoRuntime(db,load_registry(config['registry']),instances,broker,workers,config.get('factors'))
        with db.transaction() as c:c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('operations:identity',canonical({'mode':'demo','account_alias':instances[0].account.alias,'config_hashes':{i.instance_id:i.hash for i in instances}})))
        while not stopped:
            now=datetime.now(timezone.utc)
            try:
                cycle(runtime);Alerts(db).transition('demo-service',False,'BROKER_DATA_OR_RECONCILIATION_REQUIRED',now)
            except (ValueError,OSError,TimeoutError,KeyError):
                Alerts(db).transition('demo-service',True,'BROKER_DATA_OR_RECONCILIATION_REQUIRED',now)
                # Recovery remains possible when entry coverage is unavailable.
                try: broker.call('recover')
                except (ValueError,OSError,TimeoutError): pass
            time.sleep(.5)

if __name__=='__main__':main()

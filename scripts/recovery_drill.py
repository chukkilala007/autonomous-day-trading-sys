"""Local isolated recovery drill; no external account or host state."""
import json,runpy,tempfile,time
from pathlib import Path
from trading_platform.persistence.database import Database
from trading_platform.persistence.archive import backup,restore
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.simulation.broker import PaperBroker
from trading_platform.simulation.replay import load_registry


def main():
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        with Database(root/'source.db') as db:
            runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(root/'broker.json'))
            runtime.process(*rows[0]);ids={o['id'] for o in runtime.status()['orders']}
        manifest=backup(root/'source.db',root/'broker.json',root/'archive')
        begin=time.monotonic();restore(root/'archive',root/'restored')
        with Database(root/'restored'/'core.db') as db:
            runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(root/'restored'/'paper.json'))
            assert runtime.controls.state()['paused'] and runtime.reconciled
            assert {o['id'] for o in runtime.status()['orders']}==ids
            for row in rows[1:]: runtime.process(*row)
            state=runtime.status();elapsed=time.monotonic()-begin
            passed=elapsed<10 and len(state['orders'])==2 and not state['positions'] and not state['active_risk'] and runtime.controls.state()['paused']
        print(json.dumps({'passed':passed,'rpo_events':manifest['rpo_events'],'recovery_seconds':elapsed,'maximum_recovery_seconds':10,'orders':2,'remaining_positions':len(state['positions']),'restore_halt_preserved':True,'scope':'isolated local paper restore'},indent=2))
        return 0 if passed else 1

if __name__=='__main__': raise SystemExit(main())

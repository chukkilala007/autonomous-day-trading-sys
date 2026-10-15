"""Measured paper workload; acceptance limits are loaded before the run."""
import json,resource,runpy,statistics,tempfile,time
from datetime import timedelta
from pathlib import Path
from trading_platform.persistence.database import Database
from trading_platform.runtime.paper import PaperRuntime
from trading_platform.simulation.broker import PaperBroker
from trading_platform.simulation.replay import load_registry


def main():
    limits=json.loads(Path('config/soak-acceptance.json').read_text())
    instances,rows=runpy.run_path('tests/execution/test_runtime.py')['inputs']()
    latencies=[]
    with tempfile.TemporaryDirectory() as folder,Database(Path(folder)/'state.db') as db:
        runtime=PaperRuntime(db,load_registry('config/registry.json'),instances,PaperBroker(Path(folder)/'paper.json'))
        for row in rows: runtime.process(*row)
        event,snapshot,contracts=rows[-1];start=time.monotonic();number=0
        while time.monotonic()-start<limits['duration_seconds']:
            number+=1;at=snapshot.cutoff+timedelta(seconds=number)
            current=event.model_copy(update={'event_id':'soak-'+str(number),'source_time':at,'available_at':at})
            quotes=tuple(q.model_copy(update={'source_time':at,'received_at':at}) for q in snapshot.quotes)
            snap=snapshot.model_copy(update={'cutoff':at,'quotes':quotes})
            before=time.monotonic();runtime.process(current,snap,contracts);latencies.append(time.monotonic()-before)
            time.sleep(max(0,start+number/limits['events_per_second']-time.monotonic()))
        result=runtime.status()
        p95=sorted(latencies)[int(len(latencies)*.95)-1];rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        passed=(number>=limits['minimum_events'] and p95<=limits['maximum_p95_seconds'] and rss<=limits['maximum_rss_mib'] and
            len(result['orders'])==limits['expected_entry_commands'] and not result['positions'] and not result['active_risk'] and not result['rejections'] and all(not i['halt'] for i in result['instances']))
        report={'passed':passed,'limits':limits,'events':number,'elapsed_seconds':time.monotonic()-start,'p95_seconds':p95,'rss_mib':rss,'orders':len(result['orders']),'positions':len(result['positions']),'active_risk':len(result['active_risk'])}
        print(json.dumps(report,indent=2));return 0 if passed else 1

if __name__=='__main__': raise SystemExit(main())

"""Run installed attended components with synthetic broker fixtures, never credentials."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path('tests/broker').resolve()))
from twisted.internet.defer import succeed
from trading_platform.gateways.ctrader.attended_adapter import Adapter
from trading_platform.gateways.ctrader.orders import DemoTransport
from trading_platform.gateways.ctrader.execution import ExecutionLedger
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.test_cycle import advance_completed_test
from test_attended_adapter import adapter, rig, result
from test_pending_lifecycle import pending_lifecycle, test_placeholder_through_cleanup_and_review
from test_settlement_edges import test_partial_remainder_cancel_waits_for_last_exit_deal


def rss_mib():
    return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')/1048576


def main():
    limits=json.loads(Path('config/attended-soak-acceptance.json').read_text())
    start=time.monotonic();latencies=[];memory=[];writes=0
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder);cycle=0
        while time.monotonic()-start<limits['duration_seconds']:
            before=time.monotonic()
            fixture=rig.__wrapped__(path)
            x=next(fixture)
            try:
                if cycle==0:
                    a=adapter.__wrapped__(x)
                    template=a[1].approval
                    report=a[1].report
                else:
                    calls=[]
                    x.client.send=lambda request,**kw: (calls.append(request) or succeed(object()))
                    approval=template.model_copy(update={'test_id':f'soak-{cycle}'})
                    runtime=Adapter(DemoTransport(x.db,x.session,authorized=True),
                        x.binding,ExecutionLedger(x.db,12),report,approval,
                        approved_hash=digest(approval),now=lambda:x.clock[0])
                    a=(x,runtime,calls)
                a[1].approval=a[1].approval.model_copy(update={'test_id':f'soak-{cycle}'})
                a[1].approved_hash=digest(a[1].approval)
                components=pending_lifecycle.__wrapped__(a)
                if cycle%2:
                    test_partial_remainder_cancel_waits_for_last_exit_deal(components)
                    expected=3
                else:
                    test_placeholder_through_cleanup_and_review(components,'CANCELLED')
                    expected=2
                assert len(a[2])==expected
                writes+=len(a[2])
                economics=result(components[4].economics.collect())
                advance_completed_test(x.db,'12',f'soak-{cycle+1}',economics,x.clock[0])
                count=x.db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'completed-test:%'").fetchone()[0]
                assert count==cycle+1
                assert x.db.connection.execute("SELECT count(*) FROM checkpoints WHERE id LIKE 'gateway-send:%' OR id LIKE 'gateway-management:%'").fetchone()[0]==0
                assert x.db.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                checkpoint_count=x.db.connection.execute('SELECT count(*) FROM checkpoints').fetchone()[0]
            finally:
                x.db.close()
                fixture.close()
            cycle+=1
            latencies.append(time.monotonic()-before)
            memory.append(rss_mib())
            if cycle%30==0:
                print(json.dumps(dict(progress_cycles=cycle,rss_mib=memory[-1])),flush=True)
            time.sleep(max(0,start+cycle/limits['cycles_per_second']-time.monotonic()))
        warm=memory[limits['warmup_cycles']:]
        growth=max(warm)-min(warm) if warm else float('inf')
        p95=sorted(latencies)[max(0,int(len(latencies)*.95)-1)]
        passed=(cycle>=limits['minimum_cycles'] and p95<=limits['maximum_p95_seconds']
                and max(memory)<=limits['maximum_rss_mib']
                and growth<=limits['maximum_post_warmup_growth_mib'])
        report=dict(passed=passed,limits=limits,cycles=cycle,
            elapsed_seconds=time.monotonic()-start,p95_seconds=p95,
            peak_sampled_rss_mib=max(memory),post_warmup_rss_range_mib=growth,
            synthetic_writes=writes,archives=cycle,checkpoint_count=checkpoint_count,
            database_bytes=(path/'state').stat().st_size,
            unresolved_active_checkpoints=0,integrity='ok')
        print(json.dumps(report),flush=True)
        return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())

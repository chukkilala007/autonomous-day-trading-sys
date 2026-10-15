"""Evidence gate separating actual demo observations from deterministic faults."""
import argparse,json
from pathlib import Path
from trading_platform.contracts.values import digest

ACTUAL=frozenset(('authentication','metadata','entry_fill','protection','owned_exit','fees','reconciliation'))
FAULTS=frozenset(('lost_ack','duplicate_event','partial_fill','cancel_fill_race','disconnect','core_restart','stale_fence','unprotected_fill'))


def report(account,evidence):
    seen=set();verified=set();issues=[]
    for item in evidence:
        scenario=item.get('scenario')
        if scenario in seen: issues.append('duplicate scenario: '+str(scenario));continue
        seen.add(scenario)
        if str(item.get('account'))!=str(account): issues.append('account mismatch: '+str(scenario));continue
        if item.get('result')!='pass' or not item.get('artifact_hash') or not item.get('observed_at'):
            issues.append('missing successful evidence: '+str(scenario));continue
        if scenario in ACTUAL and item.get('source')!='actual_demo':
            issues.append('actual demo evidence required: '+scenario);continue
        if scenario in FAULTS and item.get('source') not in ('actual_demo','deterministic_transport'):
            issues.append('unclassified evidence: '+scenario);continue
        if item.get('unexplained_exposure',True) or item.get('duplicate_submissions',1)!=0:
            issues.append('exposure/submission invariant failed: '+str(scenario));continue
        verified.add(scenario)
    missing=sorted((ACTUAL|FAULTS)-verified)
    return {'account':str(account),'qualified':not missing and not issues,'missing':missing,'issues':issues,'evidence_hash':digest(evidence),'live_enabled':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--account',required=True);p.add_argument('--evidence',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();result=report(args.account,json.loads(Path(args.evidence).read_text()))
    with Path(args.output).open('x') as out: json.dump(result,out,indent=2)
    return 0 if result['qualified'] else 2

if __name__=='__main__': raise SystemExit(main())

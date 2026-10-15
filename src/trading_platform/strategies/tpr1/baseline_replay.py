"""Replay supported saved snapshots without backdating their later quotes."""
import argparse
from collections import Counter
import json
from pathlib import Path
from .baseline import Bar, Engine, PARAMETERS, VERSION, epoch, iso

def load_history(root):
    data={s:{tf:{} for tf in ('m1','m5','m15','h1')} for s in PARAMETERS}
    sources=[]; skipped=[]
    for path in sorted(root.glob('*/*/data-snapshot.json')):
        d=json.loads(path.read_text())
        if 'cutoff' not in d or not isinstance(d.get('symbols'),dict):
            skipped.append({'path':str(path),'reason':'UNSUPPORTED_SCHEMA'});continue
        found=False
        cutoff=epoch(d['cutoff'])
        for s in PARAMETERS:
            x=d['symbols'].get(s,{})
            if not all(isinstance(x.get(tf),dict) and 'completed' in x[tf] for tf in ('m1','m5')):
                continue
            for tf,seconds in [('m1',60),('m5',300),('m15',900),('h1',3600)]:
                if tf not in x or 'completed' not in x[tf]: continue
                for raw in x[tf]['completed']:
                    b=Bar.read(raw)
                    if b.t+seconds>cutoff:
                        raise ValueError(f'Unfinished bar in completed snapshot: {path} {s} {tf}')
                    old=data[s][tf].get(b.t)
                    if old is not None and old!=b:
                        raise ValueError(f'Conflicting OHLC: {path} {s} {tf} {iso(b.t)}')
                    data[s][tf][b.t]=b
            found=True
        (sources if found else skipped).append(str(path) if found else {'path':str(path),'reason':'UNSUPPORTED_SCHEMA'})
    return data,sources,skipped

def summarize(result):
    events=result['events']
    triggers=[e for e in events if e['event']=='TRIGGERED']
    return {'forming_candidates':len({e['candidate_id'] for e in events if e['event']=='FORMING'}),
      'completed_triggers':len(triggers),'geometry_passes':sum(e['geometry_pass'] for e in triggers),
      'geometry_rejections':sum(not e['geometry_pass'] for e in triggers),
      'geometry_passes_with_context':sum(e['geometry_pass'] and e['context_screen_complete'] for e in triggers),
      'entry_touches_unverified':sum('ENTRY_TOUCHED' in e['reason_codes'] for e in events),
      'ambiguous_touches':sum('AMBIGUOUS_TOUCH' in e['reason_codes'] for e in events),
      'reasons':dict(sorted(Counter(r for _,r in {(e['candidate_id'],r) for e in events for r in e['reason_codes']}).items())),
      'execution_verified':0,'trades_simulated':0,'pnl':None}

def main(root,output):
    data,sources,skipped=load_history(root)
    if not sources:raise ValueError('No supported snapshots')
    output.mkdir(parents=True,exist_ok=False)
    results={}
    for s,x in data.items():
        m1=[x['m1'][t] for t in sorted(x['m1'])];m5=[x['m5'][t] for t in sorted(x['m5'])]
        context={tf:[x[tf][t] for t in sorted(x[tf])] for tf in ('m15','h1')}
        r=Engine(s,m5,context=context).run(m1)
        r['coverage']={'m1':len(m1),'m5':len(m5),'first_m1':iso(m1[0].t) if m1 else None,'last_m1':iso(m1[-1].t) if m1 else None}
        results[s]=r
    summary={'version':VERSION,'sources':sources,'skipped':skipped,'parameters':PARAMETERS,
             'results':{s:summarize(r) for s,r in results.items()},
             'purpose':'pattern detection only; no historical execution/cost validation or profitability estimate'}
    (output/'events.json').write_text(json.dumps(results,indent=2))
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    rows=[]
    for s,v in summary['results'].items():
        rows.append(f"| {s} | {v['forming_candidates']} | {v['completed_triggers']} | {v['geometry_passes']} | {v['geometry_rejections']} | {v['entry_touches_unverified']} |")
    (output/'replay.md').write_text('# TPR-1 chronological detection test\n\n'
      'Historical candidate events, not live entries or completed trades. Quotes from snapshot observation times were not applied to earlier candles. '
      'Geometry uses explicit research increments and causally confirmed M5/M15/H1 levels; context completeness is recorded per trigger. Historical costs remain unknown.\n\n'
      '| Symbol | Forming candidates | Completed triggers | Geometry passes | Geometry rejections | Later entry touches, unverified |\n'
      '|---|---:|---:|---:|---:|---:|\n'+'\n'.join(rows)+'\n\n'
      f"Supported snapshots: {len(sources)}. Older unsupported snapshots: {len(skipped)} (listed in summary.json). "
      'Overlaps are deduplicated; missing intervals remain gaps. Pattern events are not independent trades. No P&L, expectancy or win rate is estimated.\n\n'
      '[Summary and provenance](summary.json) · [Candidate histories](events.json)\n')
    assert json.loads((output/'summary.json').read_text())==summary
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();main(args.root,args.output)

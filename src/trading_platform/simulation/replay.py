"""Offline causal decision replay; never reports invented execution/P&L."""
import json
from pathlib import Path
from collections import Counter
from trading_platform.contracts.events import Event
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.contracts.config import Instance
from trading_platform.contracts.values import canonical,digest
from trading_platform.registry.manifest import Manifest
from trading_platform.registry.loader import Registry
from trading_platform.runtime.scheduler import evaluate
from trading_platform.market_data.history import validate_history


def load_registry(path):
    manifests=[Manifest.model_validate_json(json.dumps(m)) for m in json.loads(Path(path).read_text())]
    return Registry({m.package:m for m in manifests})


def records(path):
    rows=json.loads(Path(path).read_text())
    result=[];seen={};previous=None;history={}
    for row in rows:
        event=Event.model_validate_json(json.dumps(row['event']))
        snapshot=Snapshot.model_validate_json(json.dumps(row['snapshot']))
        if event.event_id in seen:
            if seen[event.event_id]!=canonical(row): raise ValueError('conflicting event revision')
            continue
        seen[event.event_id]=canonical(row)
        if previous is not None and snapshot.cutoff<previous: raise ValueError('unsorted snapshots')
        if snapshot.cutoff!=event.available_at: raise ValueError('event cutoff mismatch')
        previous=snapshot.cutoff
        bars=validate_history(snapshot)
        for b in bars:
            key=(b.instrument,b.start,b.end)
            if key in history and history[key]!=b: raise ValueError('conflicting history revision')
            history[key]=b
        result.append((event,snapshot.model_copy(update={'bars':bars})))
    return result


def replay(instance,registry,rows):
    plugin=registry.load(instance);manifest=registry.reviewed[instance.strategy]
    state=plugin.initialize(instance);decisions=[]
    for event,snapshot in rows:
        result=evaluate(plugin,manifest,instance,event,snapshot,(),state)
        for d in result.decisions:
            if d.proposal: plugin.validate_proposal(d.proposal,snapshot)
        state=result.state;decisions.extend(result.decisions)
    return dict(instance=instance.instance_id,package=instance.strategy,package_digest=instance.package_digest,config_hash=instance.hash,input_hash=digest([{'event':e,'snapshot':s} for e,s in rows]),decisions=[json.loads(d.model_dump_json()) for d in decisions],state=json.loads(state),counts=dict(Counter(d.outcome for d in decisions)),pnl=None,limitation='Decision replay only; no broker fills or profitability estimate')


def run(config,registry,input_path,output):
    instance=Instance.model_validate_json(Path(config).read_text())
    if instance.mode!='paper': raise ValueError('offline replay requires paper mode')
    result=replay(instance,load_registry(registry),records(input_path))
    with Path(output).open('x') as f: f.write(canonical(result)+'\n')
    return result

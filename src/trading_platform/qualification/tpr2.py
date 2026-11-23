"""Read-only TPR-2 forward-shadow qualification assessment."""
import hashlib, json, sqlite3
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator

from trading_platform.contracts.values import Record, Name, Time, utc


class QualificationPlan(Record):
    evaluation_id: Name
    package: Literal['tpr2@1']
    package_digest: Name
    registered_at: Time
    starts_at: Time
    ends_at: Time
    maximum_extension_ends_at: Time
    instruments: tuple[Name, ...]
    minimum_decisions_per_instrument: int = Field(gt=0)
    minimum_triggers_per_instrument: int = Field(gt=0)
    minimum_natural_limit_proposals_per_instrument: int = Field(gt=0)
    maximum_unavailable_fraction: Decimal = Field(ge=0, le=1)
    required_final_connection_generation: int = Field(ge=1)
    require_zero_order_writes: Literal[True] = True
    parameters_locked: Literal[True] = True
    performance_claim_permitted: Literal[False] = False
    insufficient_sample_action: Literal['extend_without_parameter_change_until_maximum_extension_then_report_inconclusive']

    @model_validator(mode='after')
    def frozen_window(self):
        if not self.registered_at < self.starts_at < self.ends_at < self.maximum_extension_ends_at:
            raise ValueError('qualification window must be preregistered')
        if not self.instruments or len(set(self.instruments)) != len(self.instruments):
            raise ValueError('unique instruments required')
        return self


def summarize(path, instrument, gateway_report=None):
    """Read an existing stopped/copy SQLite database without modifying it."""
    connection=sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)
    connection.row_factory=sqlite3.Row
    try:
        decisions=[json.loads(row['body']) for row in connection.execute(
            "SELECT body FROM decisions WHERE instance='tpr2' ORDER BY event_seq,id")]
        outcomes=Counter(row['outcome'] for row in decisions);candidates=set();triggered=set();reason_counts=Counter()
        invalid_proposals=0;limit_proposals=0;packages=set();config_hashes=set();times=[]
        for row in decisions:
            packages.add(row['package']);config_hashes.add(row['config_hash']);times.append(utc(row['at']))
            reason_counts.update(row.get('reasons',()))
            diagnostics=json.loads(row.get('diagnostics') or '{}')
            for event in diagnostics.get('events',()):
                candidate=event.get('candidate_id')
                if candidate: candidates.add(candidate)
                if event.get('event')=='TRIGGERED' and candidate: triggered.add(candidate)
                reason_counts.update(event.get('reason_codes',()))
            proposal=row.get('proposal')
            if proposal:
                valid=(proposal.get('kind')=='entry' and proposal.get('order_type')=='limit'
                       and proposal.get('profile')=='protected' and proposal.get('target') is not None
                       and proposal.get('instrument')==instrument)
                invalid_proposals+=int(not valid);limit_proposals+=int(valid)
        provider=connection.execute("SELECT body FROM checkpoints WHERE id='operations:provider'").fetchone()
        provider=json.loads(provider['body']) if provider else {}
        gateway={};gateway_hash=None
        if gateway_report:
            raw=Path(gateway_report).read_bytes();gateway_hash=hashlib.sha256(raw).hexdigest();gateway=json.loads(raw)
            if (gateway.get('status')!='PASS' or gateway.get('mode')!='shadow'
                    or gateway.get('orders_enabled') is not False or gateway.get('order_writes')!=0
                    or gateway.get('rejected_writes')!=0):
                raise ValueError('nonpassing or write-capable gateway report')
            started,ended=utc(gateway['started_at']),utc(gateway['ended_at'])
            if times and (min(times)<started or max(times)>ended): raise ValueError('gateway/database time mismatch')
        count=lambda table:connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        return {'instrument':instrument,'decisions':len(decisions),'outcomes':dict(outcomes),
            'candidate_count':len(candidates),'trigger_count':len(triggered),'natural_limit_proposals':limit_proposals,
            'invalid_proposals':invalid_proposals,'reason_counts':dict(reason_counts),
            'packages':sorted(packages),'config_hashes':sorted(config_hashes),
            'first_decision_at':None if not times else min(times).isoformat(),
            'last_decision_at':None if not times else max(times).isoformat(),
            'final_connection_generation':gateway.get('generation',provider.get('generation')),
            'reconciled_generations':gateway.get('reconciled_generations',[]),
            'gateway_report_sha256':gateway_hash,
            'commands':count('commands'),'reservations':count('reservations'),'positions':count('positions')}
    finally: connection.close()


def assess(plan, runs, now):
    plan=plan if isinstance(plan,QualificationPlan) else QualificationPlan.model_validate(plan);now=utc(now)
    by_symbol={run['instrument']:run for run in runs};blockers=[];sample=[]
    if set(by_symbol)!=set(plan.instruments): blockers.append('INSTRUMENT_RUN_SET')
    for symbol in plan.instruments:
        run=by_symbol.get(symbol)
        if not run: continue
        if run['packages'] not in ([],[plan.package]): blockers.append(symbol+':PACKAGE_DRIFT')
        if run['invalid_proposals']: blockers.append(symbol+':INVALID_PROPOSAL')
        if run['commands'] or run['reservations'] or run['positions']: blockers.append(symbol+':ORDER_PATH_NOT_ZERO')
        if run.get('final_connection_generation') != plan.required_final_connection_generation:
            blockers.append(symbol+':RECONNECT_NOT_PROVEN')
        if run.get('reconciled_generations') != [1,plan.required_final_connection_generation]:
            blockers.append(symbol+':RECONNECT_GENERATIONS')
        if run.get('first_decision_at') and utc(run['first_decision_at']) < plan.starts_at:
            blockers.append(symbol+':PREWINDOW_CONTAMINATION')
        unavailable=run.get('outcomes',{}).get('UNAVAILABLE',0)
        fraction=Decimal(unavailable)/Decimal(run['decisions']) if run['decisions'] else Decimal(1)
        if fraction>plan.maximum_unavailable_fraction: blockers.append(symbol+':UNAVAILABLE_FRACTION')
        if run.get('reason_counts',{}).get('DATA_GAP',0): blockers.append(symbol+':DATA_GAP')
        sample += ([symbol+':DECISIONS'] if run['decisions']<plan.minimum_decisions_per_instrument else [])
        sample += ([symbol+':TRIGGERS'] if run['trigger_count']<plan.minimum_triggers_per_instrument else [])
        sample += ([symbol+':NATURAL_LIMIT_PROPOSALS'] if run['natural_limit_proposals']<plan.minimum_natural_limit_proposals_per_instrument else [])
    if blockers: status='FAIL'
    elif now<plan.ends_at: status='IN_PROGRESS'
    elif not sample and now<=plan.maximum_extension_ends_at: status='OPERATIONAL_SHADOW_PASS'
    elif now<plan.maximum_extension_ends_at: status='INCONCLUSIVE_EXTEND'
    else: status='INCONCLUSIVE'
    return {'evaluation_id':plan.evaluation_id,'status':status,'as_of':now.isoformat(),
        'blockers':blockers,'sample_shortfalls':sample,'runs':runs,
        'performance_claim':False,'orders_authorized':False,
        'interpretation':'Operational shadow qualification only; no profitability or live-readiness inference.'}


def run(plan_path, run_paths, output, now, gateway_reports=None):
    plan=QualificationPlan.model_validate_json(Path(plan_path).read_text())
    gateway_reports=dict(gateway_reports or ())
    reports=[summarize(path,symbol,gateway_reports.get(symbol)) for symbol,path in run_paths]
    result=assess(plan,reports,now)
    with Path(output).open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
    return result

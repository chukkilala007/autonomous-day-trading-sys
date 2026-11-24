import json
from datetime import datetime,timezone
from pathlib import Path
from trading_platform.qualification.tpr2 import QualificationPlan,aggregate,assess,summarize
from trading_platform.persistence.database import Database
from trading_platform.contracts.values import canonical


def plan():
    return QualificationPlan.model_validate_json(Path('config/evaluation/tpr2-shadow-v1.json').read_text())


def run(symbol,**changes):
    base={'instrument':symbol,'decisions':1000,'outcomes':{'WATCH':999,'ENTRY':1},'candidate_count':20,
        'trigger_count':10,'natural_limit_proposals':1,'invalid_proposals':0,'reason_counts':{},
        'packages':['tpr2@1'],'config_hashes':['a'*64],'first_decision_at':'2026-11-24T00:00:00Z',
        'last_decision_at':'2026-12-21T22:59:00Z','final_connection_generation':3,
        'reconciled_generations':[1,3],'gateway_report_sha256':'b'*64,
        'commands':0,'reservations':0,'positions':0}
    base.update(changes);return base


def test_preregistered_window_cannot_pass_early_and_never_claims_performance():
    result=assess(plan(),[run('EURUSD'),run('XAUUSD')],datetime(2026,12,1,tzinfo=timezone.utc))
    assert result['status']=='IN_PROGRESS' and result['performance_claim'] is False
    assert result['orders_authorized'] is False


def test_complete_operational_sample_passes_only_after_window():
    result=assess(plan(),[run('EURUSD'),run('XAUUSD')],datetime(2026,12,22,tzinfo=timezone.utc))
    assert result['status']=='OPERATIONAL_SHADOW_PASS' and not result['blockers']


def test_order_write_gap_drift_reconnect_and_sample_shortfall_fail_or_extend():
    p=plan();after=datetime(2026,12,22,tzinfo=timezone.utc)
    failed=assess(p,[run('EURUSD',commands=1),run('XAUUSD',reason_counts={'DATA_GAP':1})],after)
    assert failed['status']=='FAIL' and 'EURUSD:ORDER_PATH_NOT_ZERO' in failed['blockers']
    short=assess(p,[run('EURUSD',trigger_count=0,natural_limit_proposals=0),run('XAUUSD')],after)
    assert short['status']=='INCONCLUSIVE_EXTEND'


def test_stopped_database_summary_is_read_only_and_counts_natural_limit(tmp_path):
    path=tmp_path/'shadow.db'
    with Database(path) as db:
        decision={'package':'tpr2@1','config_hash':'a'*64,'outcome':'ENTRY','at':'2026-11-24T00:01:00Z',
            'reasons':[],'diagnostics':json.dumps({'events':[{'event':'TRIGGERED','candidate_id':'TPR-2/X'}]}),
            'proposal':{'kind':'entry','order_type':'limit','profile':'protected','target':'2','instrument':'EURUSD'}}
        db.connection.execute("INSERT INTO decisions VALUES ('d','tpr2',1,?)",(canonical(decision),))
        db.connection.execute("INSERT INTO checkpoints VALUES ('operations:provider',?)",(canonical({'generation':3}),))
    gateway=tmp_path/'gateway.json';gateway.write_text(json.dumps({'status':'PASS','mode':'shadow',
        'orders_enabled':False,'order_writes':0,'rejected_writes':0,'generation':3,
        'reconciled_generations':[1,3],'started_at':'2026-11-24T00:00:00Z',
        'ended_at':'2026-11-24T00:02:00Z'}))
    before=path.read_bytes();result=summarize(path,'EURUSD',gateway)
    assert result['natural_limit_proposals']==1 and result['trigger_count']==1
    assert result['commands']==result['reservations']==result['positions']==0
    assert result['final_connection_generation']==3 and result['reconciled_generations']==[1,3]
    assert path.read_bytes()==before


def test_multiple_bounded_runs_deduplicate_candidates_and_require_reconnects():
    first=run('EURUSD',decisions=600,candidate_count=2,trigger_count=1,natural_limit_proposals=1,
        gateway_report_sha256='1'*64,gateway_started_at='2026-11-24T00:00:00Z',gateway_ended_at='2026-11-24T01:00:00Z',
        _candidate_ids=['A','B'],_trigger_ids=['B'],_proposal_ids=['B'])
    second=run('EURUSD',decisions=500,candidate_count=2,trigger_count=1,natural_limit_proposals=1,
        gateway_report_sha256='2'*64,gateway_started_at='2026-11-24T02:00:00Z',gateway_ended_at='2026-11-24T03:00:00Z',
        _candidate_ids=['B','C'],_trigger_ids=['B'],_proposal_ids=['B'])
    result=aggregate('EURUSD',[first,second])
    assert result['run_count']==2 and result['decisions']==1100
    assert result['candidate_count']==3 and result['trigger_count']==1 and result['natural_limit_proposals']==1
    assert result['all_reconnects_proven'] is True


def test_multiple_bounded_runs_reject_overlapping_windows():
    first=run('EURUSD',gateway_started_at='2026-11-24T00:00:00Z',gateway_ended_at='2026-11-24T02:00:00Z')
    second=run('EURUSD',gateway_started_at='2026-11-24T01:00:00Z',gateway_ended_at='2026-11-24T03:00:00Z')
    import pytest
    with pytest.raises(ValueError,match='overlapping'): aggregate('EURUSD',[first,second])

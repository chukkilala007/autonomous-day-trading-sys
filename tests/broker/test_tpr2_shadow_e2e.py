import json, threading
from datetime import timedelta
from pathlib import Path

from trading_platform.contracts.config import Instance
from trading_platform.contracts.events import Bar, Event, Quote
from trading_platform.contracts.snapshots import Snapshot
from trading_platform.persistence.database import Database
from trading_platform.contracts.values import digest
from trading_platform.gateways.ctrader.pilot import PilotGate, PilotMandate
from trading_platform.registry.loader import Registry
from trading_platform.runtime.shadow import ShadowRuntime
from trading_platform.runtime.worker import Server
from trading_platform.simulation.replay import load_registry
from tests.replay.test_tpr2 import evidence
from tests.replay.test_tpr_adapter import executable_snapshot


def configured():
    raw=json.loads(Path('config/instances/tpr2.json').read_text());raw['mode']='shadow'
    raw['account'].update(alias='demo-shadow',environment='demo',broker_account='12',currency='USD')
    return Instance.model_validate_json(json.dumps(raw))


def start_worker(instance, token):
    reviewed=load_registry('config/registry.json').reviewed
    server=Server(('127.0.0.1',0),token,instance.instance_id,Registry(reviewed))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    return server,thread


def event(snapshot,name):
    payload=json.dumps({'execution_evidence_by_symbol':{'XAUUSD':evidence(snapshot.cutoff)}})
    return Event(event_id=name,kind='timer',instrument='ACCOUNT',source_time=snapshot.cutoff,
                 available_at=snapshot.cutoff,payload=payload)


def test_isolated_worker_shadow_entry_restart_and_zero_order_path(tmp_path):
    instance=configured();token='t'*40;state=tmp_path/'shadow.db';snapshot=executable_snapshot()
    server,thread=start_worker(instance,token)
    try:
        with Database(state) as db:
            runtime=ShadowRuntime(db,load_registry('config/registry.json'),[instance],
                workers={'tpr2':('127.0.0.1',server.server_address[1],token)})
            result=runtime.process(event(snapshot,'shadow-1'),snapshot,
                {'account_id':'12','history_complete':True,'positions':[]})
            assert result['submission_enabled'] is False
            decision=json.loads(db.connection.execute('SELECT body FROM decisions').fetchone()['body'])
            assert decision['outcome']=='ENTRY' and decision['proposal']['order_type']=='limit'
            assert not db.connection.execute('SELECT 1 FROM commands').fetchone()
            assert not db.connection.execute('SELECT 1 FROM reservations').fetchone()
    finally:
        server.shutdown();server.server_close();thread.join(5)

    # Restart both the isolated worker and the shadow core around durable state.
    server,thread=start_worker(instance,token)
    try:
        cutoff=snapshot.cutoff+timedelta(minutes=1)
        tail=Bar(instrument='XAUUSD',start=snapshot.cutoff,end=cutoff,available_at=cutoff,basis='bid',
                 open='108.90',high='109.00',low='108.80',close='108.90')
        quote=Quote(instrument='XAUUSD',bid='108.90',ask='108.91',source_time=cutoff,received_at=cutoff)
        next_snapshot=Snapshot(cutoff=cutoff,bars=snapshot.bars+(tail,),quotes=(quote,))
        with Database(state) as db:
            runtime=ShadowRuntime(db,load_registry('config/registry.json'),[instance],
                workers={'tpr2':('127.0.0.1',server.server_address[1],token)})
            runtime.process(event(next_snapshot,'shadow-2'),next_snapshot,
                {'account_id':'12','history_complete':True,'positions':[]})
            decisions=[json.loads(row['body']) for row in db.connection.execute('SELECT body FROM decisions')]
            assert [row['outcome'] for row in decisions].count('ENTRY')==1
            assert len(decisions)==2
            assert not db.connection.execute('SELECT 1 FROM commands').fetchone()
            assert not db.connection.execute('SELECT 1 FROM reservations').fetchone()
            assert not db.connection.execute('SELECT 1 FROM positions').fetchone()
    finally:
        server.shutdown();server.server_close();thread.join(5)


def test_natural_tpr2_decision_fits_disabled_one_entry_pilot_boundary(tmp_path):
    from trading_platform.strategies.tpr2.adapter import TPR2
    raw=json.loads(Path('config/instances/tpr2.json').read_text());raw['mode']='demo'
    raw['account'].update(alias='demo-account',environment='demo',broker_account='12',currency='USD')
    instance=Instance.model_validate_json(json.dumps(raw));snapshot=executable_snapshot();plugin=TPR2()
    decision=plugin.evaluate(instance,event(snapshot,'pilot-event'),snapshot,(),plugin.initialize(instance)).decisions[0]
    assert decision.outcome=='ENTRY' and decision.proposal.order_type=='limit'
    mandate=PilotMandate(account_id='12',account_alias='demo-account',test_id='tpr2-disabled-pilot',
        instance='tpr2',package='tpr2@1',config_hash=instance.hash,instrument='XAUUSD',quantity='.01',
        maximum_loss='5',maximum_stop_distance='10',minimum_reward_risk='2',
        maximum_decision_age_seconds=2,maximum_proposal_lifetime_seconds=120,
        valid_from=snapshot.cutoff-timedelta(seconds=1),submit_before=snapshot.cutoff+timedelta(seconds=10),
        reviewed_bundle_hash='b'*64,source_hash='c'*64,image_digest='d'*64)
    command={'id':decision.id,'instance':'tpr2','instrument':'XAUUSD','body':{'type':'entry',
        'decision':json.loads(decision.model_dump_json()),'size':{'quantity':'.01','risk':'5'}}}
    with Database(tmp_path/'pilot.db') as db:
        gate=PilotGate(db,mandate,approved_hash=digest(mandate))
        assert gate.validate(command,snapshot.cutoff).id==decision.id
        assert not db.connection.execute('SELECT 1 FROM commands').fetchone()

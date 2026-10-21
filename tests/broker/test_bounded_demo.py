from datetime import datetime, timezone, timedelta
import json
from decimal import Decimal
import pytest
from trading_platform.contracts.orders import Entry
from trading_platform.execution.bounded_demo import Plan, Observation, Exposure, Controller
from trading_platform.persistence.database import Database

T = datetime(2026, 10, 21, tzinfo=timezone.utc)


def plan():
    return Plan(test_id='test1', account_id='12', created_at=T, quantity='1000', equity='10000',
                planned_loss='5', entry=Entry(instrument='EURUSD', side='buy', order_type='limit',
                entry='1.10', worst_fill='1.10', stop='1.099', target='1.102', expires_at=T+timedelta(seconds=60)))


def obs(seconds=0, **kw):
    return Observation(account_id='12', observed_at=T+timedelta(seconds=seconds), connected=True,
                       history_complete=True, external_exposure=False, **kw)


def exposure(id='order1', quantity='1000', protected=True):
    return Exposure(id=id, owner='test1', quantity=quantity, protected=protected)


def test_cancel_once_expiry_is_not_terminal_and_restart_does_not_resend(tmp_path):
    p=plan(); path=tmp_path/'db'
    with Database(path) as db:
        c=Controller(db,p);r=c.step(obs(),T)
        assert r['actions'][0]['action']=='SUBMIT_ONCE' and not r['actions'][0]['executable']
        assert not c.step(obs(1),T+timedelta(seconds=1))['actions']
        assert not c.step(obs(19,pending=(exposure(),)),T+timedelta(seconds=19))['actions']
        assert c.step(obs(20,pending=(exposure(),)),T+timedelta(seconds=20))['actions'][0]['action']=='CANCEL_OWNED'
    with Database(path) as db:
        c=Controller(db,p)
        r=c.step(obs(61,pending=(exposure(),)),T+timedelta(seconds=61))
        assert r['status']=='EXPIRY_UNCONFIRMED' and not r['actions']
        assert c.step(obs(62,submission_terminal=True),T+timedelta(seconds=62))['status']!='COMPLETE'
        assert c.step(obs(63,submission_terminal=True,settlement_complete=True),T+timedelta(seconds=63))['status']=='COMPLETE'
        assert db.connection.execute('SELECT count(*) FROM commands').fetchone()[0]==0


def test_partial_fill_cancel_and_protection_cleanup(tmp_path):
    with Database(tmp_path/'db') as db:
        c=Controller(db,plan());c.step(obs(),T)
        r=c.step(obs(3,pending=(exposure(quantity='400'),),positions=(exposure('pos1','600',False),)),T+timedelta(seconds=3))
        assert {a['action']for a in r['actions']}=={'CANCEL_OWNED','CLOSE_OWNED'}
        assert c.step(obs(121,positions=(exposure('pos1','600',False),)),T+timedelta(seconds=121))['status']=='CLEANUP_UNCONFIRMED'


def test_protected_position_closed_at_deadline_never_assumed_flat(tmp_path):
    with Database(tmp_path/'db') as db:
        c=Controller(db,plan());c.step(obs(),T)
        assert not c.step(obs(119,positions=(exposure('pos'),)),T+timedelta(seconds=119))['actions']
        r=c.step(obs(120,positions=(exposure('pos'),)),T+timedelta(seconds=120))
        assert r['actions'][0]['action']=='CLOSE_OWNED' and r['status']=='CLEANUP_UNCONFIRMED'


@pytest.mark.parametrize('fault', ['disconnected','incomplete','stale','foreign','external','backwards','oversize'])
def test_gates_do_not_emit_new_actions(tmp_path,fault):
    with Database(tmp_path/'db') as db:
        c=Controller(db,plan());c.step(obs(),T);o=obs(3);now=T+timedelta(seconds=3)
        data=json.loads(o.model_dump_json())
        if fault=='disconnected':data['connected']=False
        if fault=='incomplete':data['history_complete']=False
        if fault=='stale':now+=timedelta(seconds=3)
        if fault=='foreign':data['account_id']='13'
        if fault=='external':data['external_exposure']=True
        if fault=='backwards':now=T-timedelta(seconds=1)
        if fault=='oversize':data['positions']=[json.loads(exposure('pos','1001').model_dump_json())]
        o=Observation.model_validate_json(json.dumps(data))
        if fault=='foreign':
            with pytest.raises(ValueError):c.step(o,now)
        else:assert not c.step(o,now)['actions']


def test_foreign_ownership_and_plan_replacement_rejected(tmp_path):
    with Database(tmp_path/'db') as db:
        c=Controller(db,plan());c.step(obs(),T)
        with pytest.raises(ValueError):c.step(obs(20,pending=(exposure().model_copy(update={'owner':'other'}),)),T+timedelta(seconds=20))
        with pytest.raises(ValueError):Controller(db,plan().model_copy(update={'planned_loss':Decimal('4')}))


@pytest.mark.parametrize('field,value',[('quantity','2000'),('planned_loss','5.01'),('equity','1000'),('mode','demo')])
def test_fixed_bounds(field,value):
    d=json.loads(plan().model_dump_json());d[field]=value
    with pytest.raises(ValueError):Plan.model_validate_json(json.dumps(d))


def test_late_start_aborts_without_submission(tmp_path):
    with Database(tmp_path/'db') as db:
        r=Controller(db,plan()).step(obs(3),T+timedelta(seconds=3))
        assert r['status']=='ABORTED' and not r['actions']


def test_late_exposure_cannot_remain_complete(tmp_path):
    with Database(tmp_path/'db') as db:
        c=Controller(db,plan());c.step(obs(),T)
        assert c.step(obs(1,submission_terminal=True,settlement_complete=True),T+timedelta(seconds=1))['status']=='COMPLETE'
        r=c.step(obs(2,positions=(exposure('late'),)),T+timedelta(seconds=2))
        assert r['status']=='POST_COMPLETION_EXPOSURE_HALT' and not r['actions']

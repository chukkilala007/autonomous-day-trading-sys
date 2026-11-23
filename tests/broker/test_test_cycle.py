import copy,json
from datetime import timedelta
import pytest
from trading_platform.persistence.database import Database
from trading_platform.contracts.values import canonical,digest
from trading_platform.gateways.ctrader.test_cycle import advance_completed_test
from test_settlement_mapping import T,fixture,call


def populate(db):
 s=call(*fixture())
 values={'attended-attempt:12':dict(owner='first',command_id='cmd',approval_hash='a'*64),
 'attended-monitor:12':dict(status='COMPLETE',completed_once=True,approval_hash='a'*64),
 'gateway-send:cmd':dict(instance='first',status='OBSERVED',fields=dict(ctidTraderAccountId=12)),
 'provider-settlement:cmd':json.loads(s.model_dump_json()),
 'broker-position:2':dict(closed=True,quantity='0',owner='first'),
 'broker-order:3':dict(terminal=True,record=dict(positionId='2')),
 'gateway-management:m':dict(status='TARGET_RESOLVED',owner='first')}
 for k,v in values.items():db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(k,canonical(v)))
 db.connection.execute('INSERT INTO halts VALUES (?,?)',('protection:2','UNCONFIRMED_BROKER_PROTECTION'))
 return dict(account_id='12',observed_at=T.isoformat(),reconciliation=dict(ctidTraderAccountId='12',order=[],position=[])),values


def test_cycle_archives_complete_history_and_prevents_reuse(tmp_path):
 with Database(tmp_path/'db') as db:
  e,values=populate(db);r=advance_completed_test(db,'12','second',e,T)
  archive=json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='completed-test:12:first'").fetchone()[0])
  assert archive['checkpoints']==values and len(archive['resolved_halts'])==1
  assert db.connection.execute("SELECT 1 FROM checkpoints WHERE id='consumed-test:12:first'").fetchone()
  assert not db.connection.execute('SELECT 1 FROM halts').fetchone()
  with pytest.raises(ValueError):advance_completed_test(db,'12','second',e,T)


@pytest.mark.parametrize('fault',['stale','exposure','account','monitor','settlement','cleanup','halt','order','reuse'])
def test_unresolved_cycles_never_rotate(tmp_path,fault):
 with Database(tmp_path/'db') as db:
  e,values=populate(db)
  if fault=='stale':e['observed_at']=(T-timedelta(seconds=3)).isoformat()
  if fault=='exposure':e['reconciliation']['position']=[{}]
  if fault=='account':e['account_id']='13'
  if fault=='monitor':db.connection.execute("DELETE FROM checkpoints WHERE id='attended-monitor:12'")
  if fault=='settlement':db.connection.execute("DELETE FROM checkpoints WHERE id='provider-settlement:cmd'")
  if fault=='cleanup':db.connection.execute("UPDATE checkpoints SET body=? WHERE id='gateway-management:m'",(canonical(dict(status='UNKNOWN',owner='first')),))
  if fault=='halt':db.connection.execute("INSERT INTO halts VALUES ('unrelated','STOP')")
  if fault=='order':db.connection.execute("UPDATE checkpoints SET body=? WHERE id='broker-order:3'",(canonical(dict(terminal=False,record=dict(positionId='2'))),))
  before=list(db.connection.execute('SELECT id,body FROM checkpoints'))
  with pytest.raises(ValueError):advance_completed_test(db,'12','first' if fault=='reuse' else 'second',e,T)
  assert [tuple(r) for r in db.connection.execute('SELECT id,body FROM checkpoints')]==[tuple(r) for r in before]


def test_transition_does_not_decode_retained_archives(tmp_path,monkeypatch):
 from trading_platform.gateways.ctrader import test_cycle
 with Database(tmp_path/'db') as db:
  e,values=populate(db)
  history=canonical(dict(immutable_history=True,payload='x'*1000000))
  for number in range(20):
   db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',
       ('completed-test:12:old-'+str(number),history))
  original=test_cycle.json.loads
  def checked(body,*args,**kwargs):
   assert 'immutable_history' not in body
   return original(body,*args,**kwargs)
  monkeypatch.setattr(test_cycle.json,'loads',checked)
  assert advance_completed_test(db,'12','second',e,T)['status']=='NEXT_CYCLE_PREPARED'
  assert db.connection.execute(
      "SELECT count(*) FROM checkpoints WHERE id GLOB 'completed-test:12:old-*'").fetchone()[0]==20


@pytest.mark.parametrize('position_status',['POSITION_STATUS_CREATED','POSITION_STATUS_CLOSED'])
def test_unfilled_zero_placeholder_created_or_closed_can_rotate(tmp_path,position_status):
 with Database(tmp_path/'db') as db:
  raw=dict(orderId='3',positionId='2',orderStatus='ORDER_STATUS_CANCELLED',executedVolume='0')
  proof=dict(account_id='12',command_id='cmd',order_id='3',owner='first',outcome='ORDER_STATUS_CANCELLED',
             observed_at=T,evidence_hash='b'*64,order_hash=digest(raw),cash_change='0',executed_quantity='0')
  values={'attended-attempt:12':dict(owner='first',command_id='cmd',approval_hash='a'*64),
          'attended-monitor:12':dict(status='COMPLETE',completed_once=True,approval_hash='a'*64),
          'gateway-send:cmd':dict(instance='first',status='OBSERVED',broker_order_id='3',fields=dict(ctidTraderAccountId=12)),
          'provider-unfilled:cmd':proof,'broker-order:3':dict(terminal=True,record=raw),
          'broker-position:2':dict(quantity='0',owner='first',record=dict(positionStatus=position_status)),
          'gateway-management:m':dict(status='TARGET_RESOLVED',owner='first')}
  for k,v in values.items():db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(k,canonical(v)))
  economics=dict(account_id='12',observed_at=T.isoformat(),reconciliation=dict(ctidTraderAccountId='12',order=[],position=[]))
  assert advance_completed_test(db,'12','second',economics,T)['status']=='NEXT_CYCLE_PREPARED'


def test_unfilled_nonterminal_zero_placeholder_cannot_rotate(tmp_path):
 with Database(tmp_path/'db') as db:
  raw=dict(orderId='3',positionId='2',orderStatus='ORDER_STATUS_CANCELLED',executedVolume='0')
  values={'attended-attempt:12':dict(owner='first',command_id='cmd',approval_hash='a'*64),
          'attended-monitor:12':dict(status='COMPLETE',completed_once=True,approval_hash='a'*64),
          'gateway-send:cmd':dict(instance='first',status='OBSERVED',broker_order_id='3',fields=dict(ctidTraderAccountId=12)),
          'provider-unfilled:cmd':dict(account_id='12',command_id='cmd',order_id='3',owner='first',outcome='ORDER_STATUS_CANCELLED',observed_at=T,evidence_hash='b'*64,order_hash=digest(raw),cash_change='0',executed_quantity='0'),
          'broker-order:3':dict(terminal=True,record=raw),'broker-position:2':dict(quantity='0',owner='first',record=dict(positionStatus='POSITION_STATUS_OPEN'))}
  for k,v in values.items():db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(k,canonical(v)))
  economics=dict(account_id='12',observed_at=T.isoformat(),reconciliation=dict(ctidTraderAccountId='12',order=[],position=[]))
  with pytest.raises(ValueError):advance_completed_test(db,'12','second',economics,T)

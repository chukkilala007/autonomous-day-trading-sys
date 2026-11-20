import copy,json
from datetime import timedelta
import pytest
from trading_platform.persistence.database import Database
from trading_platform.contracts.values import canonical
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

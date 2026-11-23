import json
from datetime import timedelta
import pytest
from trading_platform.persistence.database import Database
from trading_platform.contracts.values import canonical,digest
from trading_platform.gateways.ctrader.unfilled import certify_unfilled
from trading_platform.gateways.ctrader.management import reconcile_cleanup
from trading_platform.gateways.ctrader.test_cycle import advance_completed_test
from test_settlement_mapping import T


def fixture(db):
 fields=dict(ctidTraderAccountId=12,clientOrderId='cmd',symbolId=1,volume=1,tradeSide=1,limitPrice=99)
 order=dict(orderId='3',clientOrderId='cmd',tradeData=dict(symbolId='1',volume='1',tradeSide='BUY'),limitPrice=99,executedVolume='0',utcLastUpdateTimestamp='1000',orderStatus='ORDER_STATUS_CANCELLED')
 values={'attended-attempt:12':dict(command_id='cmd',owner='first',approval_hash='a'*64),
 'gateway-send:cmd':dict(fields=fields,instance='first',status='OBSERVED',broker_order_id='3'),
 'gateway-management:m':dict(status='UNKNOWN',request='ProtoOACancelOrderReq',fields=dict(ctidTraderAccountId=12,orderId=3),owner='first')}
 for k,v in values.items():db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',(k,canonical(v)))
 baseline=dict(account_id='12',observed_at=(T-timedelta(minutes=2)).isoformat(),account=dict(currency='USD',balance='100'),trader=dict(balanceVersion='1'),reconciliation=dict(ctidTraderAccountId='12'))
 e=dict(economics=dict(baseline,observed_at=T.isoformat()),orders=[order],deals=[],cashflows=[],history_from=baseline['observed_at'],history_to=T.isoformat())
 return baseline,e


def test_unfilled_completion_and_cancel_reconciliation_archive(tmp_path):
 with Database(tmp_path/'db') as db:
  b,e=fixture(db);p=certify_unfilled(db,'12',b,e,T)
  assert p.cash_change=='0'
  reconcile_cleanup(db,'12',T)
  assert json.loads(db.connection.execute("SELECT body FROM checkpoints WHERE id='gateway-management:m'").fetchone()[0])['status']=='TARGET_RESOLVED'
  db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',('attended-monitor:12',canonical(dict(status='COMPLETE',completed_once=True,approval_hash='a'*64))))
  assert advance_completed_test(db,'12','second',e['economics'],T)['status']=='NEXT_CYCLE_PREPARED'


def test_unfilled_review_accepts_exact_prior_archived_certificate_in_wider_history(tmp_path):
 with Database(tmp_path/'db') as db:
  b,e=fixture(db);old=dict(e['orders'][0],orderId='2',clientOrderId='old')
  proof=dict(account_id='12',command_id='old',order_id='2',owner='old-test',outcome='ORDER_STATUS_CANCELLED',observed_at=T,
             evidence_hash='b'*64,order_hash=digest(old),cash_change='0',executed_quantity='0')
  archive=dict(checkpoints={'provider-unfilled:old':proof,'broker-order:2':dict(record=old)})
  db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',('completed-test:12:old-test',canonical(archive)))
  e['orders'].insert(0,old)
  assert certify_unfilled(db,'12',b,e,T).order_id=='3'


def test_unfilled_review_rejects_changed_prior_archived_order(tmp_path):
 with Database(tmp_path/'db') as db:
  b,e=fixture(db);old=dict(e['orders'][0],orderId='2',clientOrderId='old')
  proof=dict(account_id='12',command_id='old',order_id='2',owner='old-test',outcome='ORDER_STATUS_CANCELLED',observed_at=T,
             evidence_hash='b'*64,order_hash=digest(old),cash_change='0',executed_quantity='0')
  db.connection.execute('INSERT INTO checkpoints VALUES (?,?)',('completed-test:12:old-test',canonical(dict(checkpoints={'provider-unfilled:old':proof,'broker-order:2':dict(record=old)}))))
  e['orders'].insert(0,dict(old,executedVolume='1'))
  with pytest.raises(ValueError):certify_unfilled(db,'12',b,e,T)


@pytest.mark.parametrize('fault',['fill','deal','cashflow','balance','version','stale','open','foreign','ambiguous','pending','window'])
def test_unfilled_review_rejects_unproven_completion(tmp_path,fault):
 with Database(tmp_path/'db') as db:
  b,e=fixture(db)
  if fault=='fill':e['orders'][0]['executedVolume']='1'
  if fault=='deal':e['deals']=[{}]
  if fault=='cashflow':e['cashflows']=[{}]
  if fault=='balance':e['economics']['account']=dict(currency='USD',balance='101')
  if fault=='version':e['economics']['trader']=dict(balanceVersion='2')
  if fault=='stale':e['economics']['observed_at']=(T-timedelta(seconds=3)).isoformat()
  if fault=='open':e['economics']['reconciliation']=dict(ctidTraderAccountId='12',position=[{}])
  if fault=='foreign':e['economics']['account_id']='13'
  if fault=='ambiguous':e['orders']*=2
  if fault=='pending':e['orders'][0]['orderStatus']='ORDER_STATUS_ACCEPTED'
  if fault=='window':e['history_from']=T.isoformat()
  with pytest.raises(ValueError):certify_unfilled(db,'12',b,e,T)
  assert not db.connection.execute("SELECT 1 FROM checkpoints WHERE id LIKE 'provider-unfilled:%'").fetchone()

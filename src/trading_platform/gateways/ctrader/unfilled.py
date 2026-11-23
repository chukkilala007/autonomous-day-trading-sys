"""Scoped observed completion for terminal unfilled demo orders, not position P&L."""
import json
from decimal import Decimal
from typing import Literal
from trading_platform.contracts.values import Record,Name,Time,digest,canonical,utc
from .valuation import Hash
from .execution import ExecutionLedger
from trading_platform.execution.recovery import matches


class UnfilledCertificate(Record):
    account_id: Name
    command_id: Name
    order_id: Name
    owner: Name
    outcome: Literal['ORDER_STATUS_CANCELLED','ORDER_STATUS_EXPIRED','ORDER_STATUS_REJECTED']
    observed_at: Time
    evidence_hash: Hash
    order_hash: Hash
    cash_change: Literal['0'] = '0'
    executed_quantity: Literal['0'] = '0'


def _reviewed_prior_orders(db,account):
    """Return exact terminal orders already certified in immutable cycle archives."""
    known=set()
    rows=db.connection.execute("SELECT body FROM checkpoints WHERE id LIKE ?",('completed-test:'+account+':%',))
    for row in rows:
        archive=json.loads(row['body']);checkpoints=archive.get('checkpoints',{})
        for key,value in checkpoints.items():
            if not key.startswith('provider-unfilled:'):continue
            proof=UnfilledCertificate.model_validate_json(canonical(value))
            order=checkpoints.get('broker-order:'+proof.order_id)
            if (proof.account_id!=account or not order or proof.order_hash!=digest(order.get('record'))
                    or proof.outcome!=order.get('record',{}).get('orderStatus')):
                raise ValueError('archived unfilled review mismatch')
            known.add((proof.order_id,proof.order_hash))
    return known


def certify_unfilled(db, account, baseline, evidence, now):
    """Caller collects authenticated complete history; persist only after exact checks."""
    account=str(account);e=evidence['economics'];reconcile=e['reconciliation']
    if (baseline['account_id']!=account or e['account_id']!=account
            or str(reconcile.get('ctidTraderAccountId'))!=account
            or not 0<=(now-utc(e['observed_at'])).total_seconds()<2
            or utc(evidence['history_from'])>utc(baseline['observed_at'])
            or utc(evidence['history_to'])<utc(baseline['observed_at'])
            or not 0<=(now-utc(evidence['history_to'])).total_seconds()<30
            or reconcile.get('order') or reconcile.get('position')
            or baseline['reconciliation'].get('order') or baseline['reconciliation'].get('position')
            or evidence['deals'] or evidence['cashflows']
            or e['account']['currency']!=baseline['account']['currency']
            or Decimal(e['account']['balance'])!=Decimal(baseline['account']['balance'])
            or 'balanceVersion' not in baseline['trader']
            or e['trader'].get('balanceVersion')!=baseline['trader']['balanceVersion']):
        raise ValueError('unfilled cash/exposure history unverified')
    row=db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('attended-attempt:'+account,)).fetchone()
    if not row:raise ValueError('owned attempt required')
    attempt=json.loads(row[0]);command=attempt['command_id']
    send=json.loads(db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('gateway-send:'+command,)).fetchone()[0])
    orders=evidence['orders'];candidates=[o for o in orders if matches(send['fields'],o)]
    if (len(candidates)!=1 or send['instance']!=attempt['owner']
            or str(send['fields']['ctidTraderAccountId'])!=account):raise ValueError('ambiguous unfilled history')
    order=candidates[0]
    prior=_reviewed_prior_orders(db,account)
    if any(o is not order and (str(o.get('orderId')),digest(o)) not in prior for o in orders):
        raise ValueError('ambiguous unfilled history')
    if (order.get('orderStatus') not in ('ORDER_STATUS_CANCELLED','ORDER_STATUS_EXPIRED','ORDER_STATUS_REJECTED')
            or Decimal(str(order.get('executedVolume',0)))!=0):raise ValueError('order is not terminal unfilled')
    result=UnfilledCertificate(account_id=account,command_id=command,order_id=str(order['orderId']),owner=attempt['owner'],
        outcome=order['orderStatus'],observed_at=now,evidence_hash=digest(dict(baseline=baseline,evidence=evidence)),order_hash=digest(order))
    ExecutionLedger(db,int(account)).apply(dict(ctidTraderAccountId=account,order=order))
    with db.transaction() as c:
        key='provider-unfilled:'+command;body=canonical(result)
        old=c.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
        if old:raise ValueError('unfilled review already exists')
        c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,body))
    return result

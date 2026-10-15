"""Persist broker execution facts without assuming delivery order or ownership."""
import json
from decimal import Decimal as D
from trading_platform.contracts.values import canonical,digest
from .normalization import integer


def money(raw,field):
    if field not in raw or 'moneyDigits' not in raw: return None
    digits=integer(raw['moneyDigits'])
    if not 0<=digits<=12: raise ValueError('invalid money scale')
    return D(integer(raw[field]))/(D(10)**digits)


def close_net(deal, *, signed_costs_verified=False):
    if not signed_costs_verified: return None
    detail=deal.get('closePositionDetail',{})
    values=[money(detail,k) for k in ('grossProfit','swap','commission','pnlConversionFee')]
    if any(v is None for v in values): return None
    # Broker costs are signed monetary fields; retain originals as evidence.
    return sum(values,D(0))


class ExecutionLedger:
    def __init__(self,db,account,*,signed_costs_verified=False):
        self.db=db;self.account=str(account);self.signed_costs_verified=signed_costs_verified

    def apply(self,event):
        if str(event.get('ctidTraderAccountId'))!=self.account: raise ValueError('foreign execution account')
        event_id=digest(event);order=event.get('order',{});position=event.get('position',{});deal=event.get('deal',{})
        correlation=order.get('clientOrderId')
        sends=[]
        for row in self.db.connection.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'gateway-send:%'"):
            body=json.loads(row['body'])
            if correlation and body['fields'].get('clientOrderId')==correlation: sends.append((row['id'],body))
        if len(sends)>1: raise ValueError('ambiguous order correlation')
        with self.db.transaction() as c:
            key='execution:'+event_id
            if c.execute('SELECT 1 FROM checkpoints WHERE id=?',(key,)).fetchone(): return False
            c.execute('INSERT INTO checkpoints VALUES (?,?)',(key,canonical(event)))
            owner=sends[0][1]['instance'] if sends else None
            if position:
                pid=str(position['positionId']);state_key='broker-position:'+pid
                old=c.execute('SELECT body FROM checkpoints WHERE id=?',(state_key,)).fetchone()
                prior=json.loads(old['body']) if old else None
                owner=owner or (prior or {}).get('owner')
                timestamp=integer(position.get('utcLastUpdateTimestamp',0))
                # No revision timestamp means evidence only, never authoritative overwrite.
                if timestamp>0 and (not prior or timestamp>prior['updated']):
                    raw_volume=integer(position.get('tradeData',{}).get('volume',0))
                    closed=position.get('positionStatus')=='POSITION_STATUS_CLOSED'
                    expected=sends[0][1]['fields'] if sends else (prior or {}).get('expected',{})
                    sl=position.get('stopLoss');tp=position.get('takeProfit')
                    protected=sl is not None and expected.get('stopLoss') is not None and D(str(sl))==D(str(expected['stopLoss']))
                    protected=protected and (expected.get('takeProfit') is None or (tp is not None and D(str(tp))==D(str(expected['takeProfit']))))
                    body=dict(owner=owner,updated=timestamp,quantity=str(D(raw_volume)/100),closed=closed,protected=protected,record=position,expected=expected)
                    c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',(state_key,canonical(body)))
                    if owner and raw_volume>0 and not closed and not protected:
                        c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',('protection:'+pid,'UNCONFIRMED_BROKER_PROTECTION'))
            if sends:
                send_key,body=sends[0]
                body.update(status='OBSERVED',broker_order_id=str(order['orderId']),last_event=event_id)
                c.execute('UPDATE checkpoints SET body=? WHERE id=?',(canonical(body),send_key))
            if deal:
                key='broker-deal:'+str(deal['dealId'])
                existing=c.execute('SELECT body FROM checkpoints WHERE id=?',(key,)).fetchone()
                body=canonical({'owner':owner,'record':deal,'net':close_net(deal,signed_costs_verified=self.signed_costs_verified)})
                if existing and json.loads(existing['body'])['record']!=deal: raise ValueError('conflicting deal revision requires reconciliation')
                c.execute('INSERT OR IGNORE INTO checkpoints VALUES (?,?)',(key,body))
        return True

    def owned(self,position_id,instance):
        row=self.db.connection.execute('SELECT body FROM checkpoints WHERE id=?',('broker-position:'+str(position_id),)).fetchone()
        if not row: raise ValueError('unknown position')
        body=json.loads(row['body'])
        if body['owner']!=instance or body['closed']: raise ValueError('position not owned/open')
        return body

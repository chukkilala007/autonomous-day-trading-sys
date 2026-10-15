"""Conservative broker-history matching: absence is not proof of rejection."""
import json
from decimal import Decimal as D
from trading_platform.contracts.values import canonical
from .protection import recovery_action


def matches(request,order):
    trade=order.get('tradeData',{})
    side=trade.get('tradeSide')
    if side in ('BUY','SELL'): side=1 if side=='BUY' else 2
    return (order.get('clientOrderId')==request['clientOrderId'] and
        str(trade.get('symbolId'))==str(request['symbolId']) and
        str(trade.get('volume'))==str(request['volume']) and side==request['tradeSide'] and
        D(str(order.get('limitPrice',0)))==D(str(request['limitPrice'])))


class DemoRecovery:
    def __init__(self,db,account): self.db=db;self.account=str(account)

    def reconcile(self,response,*,history_complete):
        if str(response.get('ctidTraderAccountId'))!=self.account: raise ValueError('foreign reconciliation')
        results={}
        with self.db.transaction() as c:
            for row in c.execute("SELECT id,body FROM checkpoints WHERE id LIKE 'gateway-send:%'").fetchall():
                body=json.loads(row['body'])
                if body['status']!='UNKNOWN': continue
                candidates=[o for o in response.get('order',[]) if matches(body['fields'],o)]
                if history_complete and len(candidates)==1:
                    body.update(status='OBSERVED',broker_order_id=str(candidates[0]['orderId']))
                    c.execute('UPDATE checkpoints SET body=? WHERE id=?',(canonical(body),row['id']))
                    results[row['id']]='OBSERVED'
                else:
                    results[row['id']]='UNRESOLVED'
                    c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',(row['id'],'INCONCLUSIVE_BROKER_HISTORY'))
        return results

    def protection(self,position_id,**facts):
        action=recovery_action(**facts)
        with self.db.transaction() as c:
            c.execute('INSERT OR REPLACE INTO checkpoints VALUES (?,?)',('recovery:'+str(position_id),canonical({'action':action,'facts':facts,'confirmed':action=='PROTECTED'})))
            if facts['owned'] and action!='PROTECTED':
                c.execute('INSERT OR REPLACE INTO halts VALUES (?,?)',('recovery:'+str(position_id),action))
        return action
